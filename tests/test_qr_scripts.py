import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))  # qr_trial imports make_qr_cards


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cards = load("make_qr_cards")
trial = load("qr_trial")


def in_frame(card, w=640, h=480):
    """Puts a rendered card in the middle of a white camera-sized frame (BGR)."""
    frame = np.full((h, w), 255, np.uint8)
    y, x = (h - card.shape[0]) // 2, (w - card.shape[1]) // 2
    frame[y : y + card.shape[0], x : x + card.shape[1]] = card
    return np.dstack([frame] * 3)


def test_short_id_fits_the_smallest_qr():
    assert cards.qr_matrix("SS-0001").shape == (21, 21)


def test_card_has_the_requested_symbol_width():
    card = cards.render(cards.qr_matrix("SS-0001"), 10, 300, quiet_cells=0)
    assert abs(card.shape[1] - 10 / 2.54 * 300) <= 21  # whole pixels per module: off by under one pixel each


def test_aruco_id_is_the_number_in_the_worker_id():
    assert cards.aruco_id("SS-0007") == 7
    with pytest.raises(ValueError):
        cards.aruco_id("SS-0050")


def test_printed_qr_card_reads_back_with_both_detectors():
    card = cards.render(cards.qr_matrix("SS-0001"), 5, 100, cards.QUIET_CELLS["qr"])
    result = trial.read_codes(trial.make_detectors("qr"), in_frame(card))
    assert {name: [text for text, _ in codes] for name, (codes, _) in result.items()} == {
        "opencv_qr": ["SS-0001"],
        "opencv_qr_aruco": ["SS-0001"],
    }


def test_printed_aruco_card_reads_back():
    card = cards.render(cards.aruco_matrix(cards.aruco_id("SS-0001")), 5, 100, cards.QUIET_CELLS["aruco"])
    (codes, _), = trial.read_codes(trial.make_detectors("aruco"), in_frame(card)).values()
    assert [text for text, _ in codes] == ["1"]


def test_summary_counts_reads_per_detector():
    rows = [
        {"detector": "a", "read": True, "seconds": 0.4},
        {"detector": "a", "read": False, "seconds": ""},
        {"detector": "a", "read": True, "seconds": 1.0},
        {"detector": "b", "read": False, "seconds": ""},
    ]
    assert trial.summarize(rows) == {"a": (2, 3, 0.7), "b": (0, 1, None)}
