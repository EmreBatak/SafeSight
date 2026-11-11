"""Sends finished checks with their snapshot to the API (POST /checks) without blocking the camera.

If the API cannot be reached the check is not lost: it is written to snapshots/unsent/ as a JSON
file and a JPEG, to be sent again later (resending is not automated yet).
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import cv2
import httpx
import numpy as np

from decision.engine import Check


def check_form(check: Check, station: str, ended_at: datetime) -> dict[str, str]:
    started_at = ended_at - timedelta(seconds=check.duration_s)
    return {
        "badge_no": check.badge_no,
        "station": station,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "attempts": str(check.attempts),
        "decision": check.decision,
        "reason": check.reason,
        "proper_ratio": str(check.proper_ratio),
    }


class Reporter:
    def __init__(self, api_url: str, station: str, unsent_dir: Path, on_status: Callable[[str], None] = print):
        self.api_url = api_url.rstrip("/")
        self.station = station
        self.unsent_dir = unsent_dir
        self.on_status = on_status

    def send(self, check: Check, frame: np.ndarray) -> threading.Thread:
        ended_at = datetime.now().astimezone()  # local time with offset, stored as timestamptz
        form = check_form(check, self.station, ended_at)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = jpeg.tobytes() if ok else b""
        thread = threading.Thread(target=self._post, args=(form, data), daemon=True)
        thread.start()
        return thread

    def _post(self, form: dict[str, str], jpeg: bytes) -> None:
        files = {"snapshot": ("snapshot.jpg", jpeg, "image/jpeg")} if jpeg else None
        try:
            response = httpx.post(f"{self.api_url}/checks", data=form, files=files, timeout=5.0)
            response.raise_for_status()
            self.on_status(f"Kayıt gönderildi (#{response.json()['id']}).")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self._save_unsent(form, jpeg)
            self.on_status(f"Kayıt gönderilemedi, yerelde saklandı: {exc}")

    def _save_unsent(self, form: dict[str, str], jpeg: bytes) -> None:
        self.unsent_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{form['ended_at'][:19].replace(':', '-')}_{form['badge_no']}"
        (self.unsent_dir / f"{stem}.json").write_text(json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8")
        if jpeg:
            (self.unsent_dir / f"{stem}.jpg").write_bytes(jpeg)
