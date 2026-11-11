import json
from datetime import datetime, timedelta, timezone

import numpy as np

from decision.engine import Check
from station.reporter import Reporter, check_form

CHECK = Check(badge_no="SS-0001", decision="REJECTED", reason="no_mask", attempts=3, proper_ratio=0.2, duration_s=12.5)


def test_form_start_time_is_end_minus_duration():
    end = datetime(2026, 11, 10, 8, 0, 30, tzinfo=timezone(timedelta(hours=3)))
    form = check_form(CHECK, "Giriş A", end)
    assert datetime.fromisoformat(form["started_at"]) == end - timedelta(seconds=12.5)
    assert form["decision"] == "REJECTED" and form["reason"] == "no_mask" and form["attempts"] == "3"


def test_check_is_kept_locally_when_api_is_down(tmp_path):
    messages = []
    # port 9 (discard) has no HTTP server, so the request fails fast
    reporter = Reporter("http://127.0.0.1:9", "Giriş A", tmp_path, messages.append)
    reporter.send(CHECK, np.zeros((48, 64, 3), np.uint8)).join(timeout=10)
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text(encoding="utf-8"))["badge_no"] == "SS-0001"
    assert len(list(tmp_path.glob("*.jpg"))) == 1
    assert messages and "gönderilemedi" in messages[0]
