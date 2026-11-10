from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.db import Worker
from api.import_workers import import_workers
from api.main import create_app

T0 = datetime(2026, 11, 10, 8, 0, tzinfo=timezone(timedelta(hours=3)))


@pytest.fixture
def client(tmp_path):
    db = f"sqlite:///{tmp_path / 'test.db'}"
    csv = tmp_path / "workers.csv"
    csv.write_text("badge_no,name,department,photo\nSS-0001,Ali Veli,Üretim,workers/SS-0001.jpg\n", encoding="utf-8")
    import_workers(csv, db)
    app = create_app(db, tmp_path / "snapshots")
    app.state.snapshots = tmp_path / "snapshots"
    return TestClient(app)


def post_check(client, decision="APPROVED", reason="proper", minutes=0, badge="SS-0001", snapshot=None):
    start = T0 + timedelta(minutes=minutes)
    form = {
        "badge_no": badge,
        "station": "Giriş A",
        "started_at": start.isoformat(),
        "ended_at": (start + timedelta(seconds=4)).isoformat(),
        "attempts": "1" if decision == "APPROVED" else "3",
        "decision": decision,
        "reason": reason,
        "proper_ratio": "0.93",
    }
    files = {"snapshot": ("s.jpg", snapshot, "image/jpeg")} if snapshot else None
    return client.post("/checks", data=form, files=files)


def test_approved_check_is_saved_with_entry_time(client):
    r = post_check(client)
    assert r.status_code == 201
    body = r.json()
    assert body["worker_name"] == "Ali Veli"
    assert body["station"] == "Giriş A"
    assert body["review_status"] is None
    listed = client.get("/checks").json()
    assert [c["id"] for c in listed] == [body["id"]]


def test_rejected_check_waits_for_review_and_keeps_snapshot(client):
    r = post_check(client, "REJECTED", "no_mask", snapshot=b"\xff\xd8jpeg")
    body = r.json()
    assert body["review_status"] == "pending"
    saved = client.app.state.snapshots / body["snapshot_path"]
    assert saved.read_bytes() == b"\xff\xd8jpeg"
    assert [c["id"] for c in client.get("/checks", params={"review_status": "pending"}).json()] == [body["id"]]


def test_unknown_badge_is_refused(client):
    assert post_check(client, badge="SS-9999").status_code == 404


def test_bad_decision_is_refused(client):
    assert post_check(client, decision="MAYBE").status_code == 422


def test_review_confirms_or_overturns_rejections_only(client):
    rejected = post_check(client, "REJECTED", "improper").json()
    r = client.patch(f"/checks/{rejected['id']}/review", json={"status": "overturned", "reviewed_by": "isg", "note": "maske doğru"})
    assert r.status_code == 200
    assert r.json()["review_status"] == "overturned"
    assert r.json()["reviewed_at"] is not None
    approved = post_check(client, minutes=5).json()
    assert client.patch(f"/checks/{approved['id']}/review", json={"status": "confirmed", "reviewed_by": "isg"}).status_code == 409


def test_alert_after_three_rejections_in_a_row(client):
    post_check(client, "REJECTED", "no_mask", minutes=0)
    post_check(client, "APPROVED", "proper", minutes=1)  # breaks the streak
    post_check(client, "REJECTED", "no_mask", minutes=2)
    post_check(client, "REJECTED", "no_mask", minutes=3)
    assert client.get("/alerts").json() == []
    third = post_check(client, "REJECTED", "improper", minutes=4).json()
    alerts = client.get("/alerts").json()
    assert [(a["check_id"], a["type"]) for a in alerts] == [(third["id"], "repeated_rejection")]
    post_check(client, "REJECTED", "no_mask", minutes=5)  # 4th in a row: no new alert yet
    assert len(client.get("/alerts").json()) == 1


def test_import_updates_existing_workers(tmp_path):
    db = f"sqlite:///{tmp_path / 'w.db'}"
    csv = tmp_path / "workers.csv"
    csv.write_text("badge_no,name,department,photo\nSS-0001,Ali,A,\n", encoding="utf-8")
    assert import_workers(csv, db) == (1, 0)
    csv.write_text("badge_no;name;department;photo\nSS-0001;Ali Veli;B;\nSS-0002;Ayşe;C;\n", encoding="utf-8")
    assert import_workers(csv, db) == (1, 1)

    from api.db import make_sessionmaker

    with make_sessionmaker(db)() as session:
        names = {w.badge_no: (w.name, w.department) for w in session.query(Worker)}
    assert names == {"SS-0001": ("Ali Veli", "B"), "SS-0002": ("Ayşe", "C")}
