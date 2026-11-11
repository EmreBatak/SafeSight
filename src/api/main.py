"""FastAPI service the station sends finished checks to, and the panel will read from (CLAUDE.md §5).

Run with `python -m api` (needs the database from docker-compose.yml).
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.db import Alert, Check, Station, Worker, make_sessionmaker

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ("APPROVED", "REJECTED")
REASONS = ("proper", "improper", "no_mask", "no_helmet", "no_face", "multiple_people")
ALERT_AFTER = 3  # consecutive REJECTED checks of one worker (CLAUDE.md §3)


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    badge_no: str
    worker_name: str
    station: str
    started_at: datetime
    ended_at: datetime
    attempts: int
    decision: str
    reason: str
    proper_ratio: float
    snapshot_path: str | None
    review_status: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    worker_id: int
    check_id: int
    type: str
    created_at: datetime
    acknowledged: bool


class ReviewIn(BaseModel):
    status: Literal["confirmed", "overturned"]
    reviewed_by: str
    note: str | None = None


def create_app(db_url: str | None = None, snapshot_dir: Path | None = None) -> FastAPI:
    sessions: sessionmaker = make_sessionmaker(db_url)
    snapshots = snapshot_dir or Path(os.environ.get("SAFESIGHT_SNAPSHOTS", ROOT / "snapshots"))
    app = FastAPI(title="SafeSight API")

    def db():
        with sessions() as session:
            yield session

    def check_out(check: Check, session: Session) -> CheckOut:
        worker = session.get(Worker, check.worker_id)
        station = session.get(Station, check.station_id)
        return CheckOut(
            **{k: getattr(check, k) for k in CheckOut.model_fields if hasattr(check, k)},
            badge_no=worker.badge_no,
            worker_name=worker.name,
            station=station.name,
        )

    @app.post("/checks", response_model=CheckOut, status_code=201)
    def create_check(
        badge_no: str = Form(...),
        station: str = Form(...),
        started_at: datetime = Form(...),
        ended_at: datetime = Form(...),
        attempts: int = Form(...),
        decision: str = Form(...),
        reason: str = Form(...),
        proper_ratio: float = Form(...),
        snapshot: UploadFile | None = File(None),
        session: Session = Depends(db),
    ):
        if decision not in DECISIONS:
            raise HTTPException(422, f"decision must be one of {DECISIONS}")
        if reason not in REASONS:
            raise HTTPException(422, f"reason must be one of {REASONS}")
        worker = session.scalar(select(Worker).where(Worker.badge_no == badge_no))
        if worker is None:
            raise HTTPException(404, f"unknown badge_no {badge_no!r}; import workers first")
        st = session.scalar(select(Station).where(Station.name == station))
        if st is None:
            st = Station(name=station)
            session.add(st)
            session.flush()

        check = Check(
            worker_id=worker.id,
            station_id=st.id,
            started_at=started_at,
            ended_at=ended_at,
            attempts=attempts,
            decision=decision,
            reason=reason,
            proper_ratio=proper_ratio,
            review_status="pending" if decision == "REJECTED" else None,
        )
        session.add(check)
        session.flush()  # assigns check.id for the snapshot file name

        if snapshot is not None:
            folder = snapshots / ended_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{check.id}.jpg"
            path.write_bytes(snapshot.file.read())
            check.snapshot_path = str(path.relative_to(snapshots))

        if decision == "REJECTED" and _rejection_streak(session, worker.id) % ALERT_AFTER == 0:
            session.add(
                Alert(
                    worker_id=worker.id,
                    check_id=check.id,
                    type="repeated_rejection",
                    created_at=datetime.now(timezone.utc),
                )
            )
        session.commit()
        return check_out(check, session)

    @app.get("/checks", response_model=list[CheckOut])
    def list_checks(
        decision: str | None = None,
        review_status: str | None = None,
        limit: int = 100,
        session: Session = Depends(db),
    ):
        query = select(Check).order_by(Check.started_at.desc()).limit(min(limit, 1000))
        if decision:
            query = query.where(Check.decision == decision)
        if review_status:
            query = query.where(Check.review_status == review_status)
        return [check_out(c, session) for c in session.scalars(query)]

    @app.patch("/checks/{check_id}/review", response_model=CheckOut)
    def review_check(check_id: int, review: ReviewIn, session: Session = Depends(db)):
        check = session.get(Check, check_id)
        if check is None:
            raise HTTPException(404, "check not found")
        if check.decision != "REJECTED":
            raise HTTPException(409, "only rejected checks are reviewed")
        check.review_status = review.status
        check.reviewed_by = review.reviewed_by
        check.reviewed_at = datetime.now(timezone.utc)
        check.review_note = review.note
        session.commit()
        return check_out(check, session)

    @app.get("/alerts", response_model=list[AlertOut])
    def list_alerts(acknowledged: bool | None = None, session: Session = Depends(db)):
        query = select(Alert).order_by(Alert.created_at.desc())
        if acknowledged is not None:
            query = query.where(Alert.acknowledged == acknowledged)
        return list(session.scalars(query))

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def _rejection_streak(session: Session, worker_id: int) -> int:
    """How many of the worker's newest checks in a row are REJECTED."""
    decisions = session.scalars(
        select(Check.decision).where(Check.worker_id == worker_id).order_by(Check.started_at.desc(), Check.id.desc())
    )
    streak = 0
    for decision in decisions:
        if decision != "REJECTED":
            break
        streak += 1
    return streak
