import pytest

from decision import Engine, Rules, State, observe
from decision.engine import IMPROPER, MULTIPLE, NO_FACE, NO_MASK, PROPER

WORKER = {"name": "Test"}


def started(rules=Rules()):
    engine = Engine(rules)
    engine.card("SS-0001", WORKER, now=0.0)
    return engine


def feed(engine, seen, n, t0=0.0):
    for i in range(n):
        engine.frame(seen, now=t0 + i * 0.1)


def test_frame_with_one_confident_detection_is_that_class():
    assert observe([("mask_proper", 0.9)], 0.7) == PROPER


def test_detections_below_the_threshold_do_not_count():
    assert observe([("mask_proper", 0.69)], 0.7) == NO_FACE
    assert observe([("mask_proper", 0.9), ("no_mask", 0.3)], 0.7) == PROPER


def test_two_confident_faces_are_multiple_people():
    assert observe([("mask_proper", 0.9), ("no_mask", 0.8)], 0.7) == MULTIPLE


def test_card_starts_a_check_and_unknown_card_does_not():
    assert started().state is State.SCANNING
    engine = Engine()
    engine.card("SS-9999", None, now=0.0)
    assert engine.state is State.UNKNOWN_CARD
    engine.tick(now=10.0)
    assert engine.state is State.IDLE


def test_fifteen_proper_frames_approve():
    engine = started()
    feed(engine, PROPER, 14)
    assert engine.state is State.SCANNING
    engine.frame(PROPER, now=1.5)
    assert engine.state is State.APPROVED
    assert engine.result.decision == "APPROVED" and engine.result.attempts == 1
    assert engine.result.proper_ratio == 1.0


def test_eighty_percent_with_a_proper_tail_approves():
    engine = started()
    feed(engine, NO_MASK, 3)  # 12 of the 15 are proper and the last 5 are proper
    feed(engine, PROPER, 12)
    assert engine.state is State.APPROVED


def test_a_bad_frame_among_the_last_five_blocks_approval():
    engine = started()
    feed(engine, PROPER, 13)
    engine.frame(IMPROPER, now=1.4)
    engine.frame(PROPER, now=1.5)
    assert engine.state is State.SCANNING  # 14/15 proper but the last five are not all proper


def test_attempt_fails_after_max_observations_and_says_why():
    engine = started()
    feed(engine, IMPROPER, Rules().max_observations)
    assert engine.state is State.RETRY
    assert engine.reason == IMPROPER and engine.attempt == 2


def test_retry_screen_then_a_fresh_attempt():
    engine = started()
    feed(engine, NO_MASK, 30)
    engine.frame(PROPER, now=3.5)  # ignored while the retry message shows
    engine.tick(now=3.5)
    assert engine.state is State.RETRY
    engine.tick(now=10.0)
    assert engine.state is State.SCANNING and engine.observations == []


def test_three_failed_attempts_reject_with_the_main_reason():
    engine = started()
    for attempt in range(3):
        engine.tick(now=attempt * 10.0)  # leaves the retry screen before attempts 2 and 3
        feed(engine, NO_FACE, 20, t0=attempt * 10.0)
        feed(engine, NO_MASK, 10, t0=attempt * 10.0 + 2)  # the last 15: 10 no_mask, 5 no_face
    assert engine.state is State.REJECTED
    assert engine.result.decision == "REJECTED"
    assert engine.result.reason == "no_mask" and engine.result.attempts == 3


def test_station_is_free_again_after_the_result():
    engine = started()
    feed(engine, PROPER, 15)
    engine.card("SS-0002", WORKER, now=2.0)  # ignored while the result shows
    assert engine.badge_no == "SS-0001"
    engine.tick(now=10.0)
    assert engine.state is State.IDLE and engine.worker is None


def test_rules_must_leave_room_for_a_full_window():
    with pytest.raises(ValueError):
        Engine(Rules(window=15, max_observations=10))


# Hard hat check (CLAUDE.md §3): a frame counts only if the mask is proper and one head wears a helmet.
from decision.engine import NO_HELMET  # noqa: E402

MASK_OK = [("mask_proper", 0.9)]


def test_helmet_check_off_ignores_heads():
    assert observe(MASK_OK, 0.7) == PROPER
    assert observe(MASK_OK, 0.7, None) == PROPER


def test_proper_mask_with_helmet_is_proper():
    assert observe(MASK_OK, 0.7, [("helmet", 0.8)]) == PROPER


def test_bare_or_missing_head_is_no_helmet():
    assert observe(MASK_OK, 0.7, [("no_helmet", 0.9)]) == NO_HELMET
    assert observe(MASK_OK, 0.7, []) == NO_HELMET
    assert observe(MASK_OK, 0.7, [("helmet", 0.5)]) == NO_HELMET  # below the threshold


def test_helmet_threshold_can_differ_from_mask_threshold():
    assert observe(MASK_OK, 0.7, [("helmet", 0.5)], helmet_min_conf=0.4) == PROPER


def test_two_heads_are_multiple_people():
    assert observe(MASK_OK, 0.7, [("helmet", 0.9), ("no_helmet", 0.8)]) == MULTIPLE


def test_mask_problems_come_before_the_helmet():
    assert observe([("no_mask", 0.9)], 0.7, [("no_helmet", 0.9)]) == NO_MASK
    assert observe([("mask_improper", 0.9)], 0.7, [("helmet", 0.9)]) == IMPROPER
    assert observe([], 0.7, [("helmet", 0.9)]) == NO_FACE


def test_check_without_helmet_is_rejected_as_no_helmet():
    rules = Rules()
    engine = started(rules)
    for attempt in range(rules.attempts):
        engine.tick(now=attempt * 100.0)  # leaves the retry screen before attempts 2 and 3
        feed(engine, NO_HELMET, rules.max_observations, t0=attempt * 100.0)
    assert engine.state is State.REJECTED
    assert engine.result.reason == "no_helmet"
