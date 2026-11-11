from decision import State
from decision.engine import IMPROPER, MULTIPLE, NO_FACE, NO_MASK
from station.ui.messages import View, message
from station.workers import Worker, load_workers


def test_worker_list_reads_comma_csv(tmp_path):
    path = tmp_path / "workers.csv"
    path.write_text("badge_no,name,department,photo\nSS-0001,Emre Batak,Test,workers/a.jpg\n", encoding="utf-8")
    worker = load_workers(path)["SS-0001"]
    assert worker.name == "Emre Batak" and worker.department == "Test"
    assert worker.photo == tmp_path / "workers" / "a.jpg"


def test_worker_list_reads_excel_semicolon_csv_with_bom(tmp_path):
    path = tmp_path / "workers.csv"
    path.write_text("badge_no;name;department;photo\nSS-0002;Yunus Emre Köybaşı;;\n", encoding="utf-8-sig")
    worker = load_workers(path)["SS-0002"]
    assert worker.name == "Yunus Emre Köybaşı" and worker.photo is None


def test_initials_use_the_first_two_names():
    assert Worker("SS-0002", "Yunus Emre Köybaşı").initials == "YE"


def test_idle_screen_asks_for_the_card():
    assert message(View(State.IDLE))[1] == "Kartını göster"


def test_retry_screen_says_what_to_fix():
    assert message(View(State.RETRY, reason=IMPROPER))[1] == "Maskeni düzelt"
    assert message(View(State.RETRY, reason=NO_MASK))[1] == "Maskeni tak"
    assert message(View(State.RETRY, reason=MULTIPLE))[1] == "Tek kişi olmalı"


def test_scanning_hint_follows_the_latest_frame():
    assert "yalnızca sen" in message(View(State.SCANNING, last_seen=MULTIPLE))[2]
    assert "Kameraya dön" in message(View(State.SCANNING, last_seen=NO_FACE))[2]


def test_result_screens_use_the_result_tones():
    assert message(View(State.APPROVED))[0] == "success"
    assert message(View(State.REJECTED))[0] == "danger"


def test_helmet_wording():
    from decision.engine import NO_HELMET

    assert message(View(State.RETRY, reason=NO_HELMET))[1] == "Kaskını tak"
    assert "Kaskını tak" not in message(View(State.SCANNING))[1]
    assert message(View(State.SCANNING, helmet_check=True))[1] == "Maske ve kask kontrol ediliyor…"
    assert "kask" in message(View(State.APPROVED, helmet_check=True))[2]
    assert "kask" not in message(View(State.APPROVED))[2]
