"""The station's check flow and approval rule (CLAUDE.md §3).

A check starts when a worker's card is read. Each attempt collects one observation per frame; the
attempt is approved once the newest `window` observations are at least `proper_ratio` mask_proper
and the newest `last_proper` are all mask_proper. If that has not happened after
`max_observations`, the attempt fails (fail-closed) and the screen says why before the next one.
After `attempts` failed attempts the check is rejected and goes to human review.

Times are passed in by the caller (seconds from any monotonic clock), so the flow is testable
without a camera or a real clock.
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any

PROPER, IMPROPER, NO_MASK = "mask_proper", "mask_improper", "no_mask"
NO_FACE, MULTIPLE = "no_face", "multiple_people"
HELMET, NO_HELMET = "helmet", "no_helmet"  # helmet model classes; NO_HELMET is also a failure reason

# Values for checks.reason in the database (CLAUDE.md §5).
REASONS = {
    PROPER: "proper",
    IMPROPER: "improper",
    NO_MASK: "no_mask",
    NO_HELMET: "no_helmet",
    NO_FACE: "no_face",
    MULTIPLE: "multiple_people",
}
# When failed observations tie, the more actionable reason is shown.
_REASON_ORDER = [MULTIPLE, NO_MASK, IMPROPER, NO_HELMET, NO_FACE]


@dataclass(frozen=True)
class Rules:
    window: int = 15  # observations the approval looks at
    proper_ratio: float = 0.8  # share of the window that must be mask_proper
    last_proper: int = 5  # the newest observations that must all be mask_proper
    min_conf: float = 0.7  # mask detections below this do not count
    helmet_min_conf: float = 0.7  # helmet detections below this do not count
    max_observations: int = 30  # an attempt fails if not approved by then (~3 s at 10 FPS)
    attempts: int = 3
    feedback_s: float = 3.0  # how long "fix your mask" shows before the next attempt
    result_s: float = 4.0  # how long the final result shows before the station is free again


def observe(
    detections: list[tuple[str, float]],
    min_conf: float,
    helmet: list[tuple[str, float]] | None = None,
    helmet_min_conf: float | None = None,
) -> str:
    """One frame's detections [(class name, confidence)] -> one observation.

    The mask decides first: no_face, multiple_people, mask_improper or no_mask. With the helmet check
    on (`helmet` is the helmet model's detections, not None), a mask_proper frame only stays
    mask_proper if exactly one confident head is seen and it wears a helmet; a bare or missing head
    is no_helmet (fail-closed), two heads are multiple_people.
    """
    counted = [label for label, conf in detections if conf >= min_conf]
    if not counted:
        return NO_FACE
    if len(counted) > 1:
        return MULTIPLE
    seen = counted[0]
    if helmet is None or seen != PROPER:
        return seen
    threshold = min_conf if helmet_min_conf is None else helmet_min_conf
    heads = [label for label, conf in helmet if conf >= threshold]
    if len(heads) > 1:
        return MULTIPLE
    return PROPER if heads == [HELMET] else NO_HELMET


class State(str, Enum):
    IDLE = "idle"  # waiting for a card
    UNKNOWN_CARD = "unknown_card"  # a card was read that is not in the worker list
    SCANNING = "scanning"  # an attempt is collecting observations
    RETRY = "retry"  # an attempt failed; showing why before the next one
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Check:
    """A finished check, shaped like a row of the checks table."""

    badge_no: str
    decision: str  # 'APPROVED' | 'REJECTED'
    reason: str  # one of REASONS' values
    attempts: int
    proper_ratio: float
    duration_s: float


class Engine:
    def __init__(self, rules: Rules = Rules()):
        if rules.max_observations < rules.window:
            raise ValueError("max_observations must be at least window")
        self.rules = rules
        self.state = State.IDLE
        self.badge_no = ""
        self.worker: Any = None  # whatever the caller looked the badge up to; shown on screen
        self.attempt = 0
        self.observations: list[str] = []
        self.reason = ""  # why the last attempt failed (a key of REASONS)
        self.result: Check | None = None
        self._started = 0.0
        self._until = 0.0

    @property
    def recent(self) -> list[str]:
        return self.observations[-self.rules.window :]

    @property
    def proper_count(self) -> int:
        """mask_proper observations in the current window, for the progress bar."""
        return self.recent.count(PROPER)

    def card(self, badge_no: str, worker: Any, now: float) -> None:
        """A card was read. Starts a check if the station is free; worker is None for unknown cards."""
        if self.state is not State.IDLE:
            return
        self.badge_no, self.worker, self.result = badge_no, worker, None
        if worker is None:
            self._enter(State.UNKNOWN_CARD, now + self.rules.feedback_s)
            return
        self._started = now
        self.attempt = 1
        self._start_attempt()

    def frame(self, seen: str, now: float) -> None:
        """One observation from observe(). Ignored unless an attempt is running."""
        if self.state is not State.SCANNING:
            return
        self.observations.append(seen)
        r = self.rules
        recent = self.recent
        if (
            len(recent) == r.window
            and recent.count(PROPER) >= r.proper_ratio * r.window
            and all(o == PROPER for o in recent[-r.last_proper :])
        ):
            self._finish("APPROVED", PROPER, now)
        elif len(self.observations) >= r.max_observations:
            self.reason = self._failure_reason()
            if self.attempt >= r.attempts:
                self._finish("REJECTED", self.reason, now)
            else:
                self.attempt += 1
                self._enter(State.RETRY, now + r.feedback_s)

    def tick(self, now: float) -> None:
        """Moves on from timed screens; call it once per frame."""
        if now < self._until:
            return
        if self.state is State.RETRY:
            self._start_attempt()
        elif self.state in (State.APPROVED, State.REJECTED, State.UNKNOWN_CARD):
            self.state, self.badge_no, self.worker, self.attempt = State.IDLE, "", None, 0
            self.observations, self.reason = [], ""

    def _start_attempt(self) -> None:
        self.observations = []
        self.state = State.SCANNING

    def _enter(self, state: State, until: float) -> None:
        self.state, self._until = state, until

    def _failure_reason(self) -> str:
        failed = Counter(o for o in self.recent if o != PROPER)
        if not failed:  # cannot happen while max_observations >= window; fail closed anyway
            return IMPROPER
        top = max(failed.values())
        return next(reason for reason in _REASON_ORDER if failed[reason] == top)

    def _finish(self, decision: str, reason: str, now: float) -> None:
        self.reason = reason
        self.result = Check(
            badge_no=self.badge_no,
            decision=decision,
            reason=REASONS[reason],
            attempts=self.attempt,
            proper_ratio=round(self.proper_count / self.rules.window, 3),
            duration_s=round(now - self._started, 2),
        )
        self._enter(State.APPROVED if decision == "APPROVED" else State.REJECTED, now + self.rules.result_s)
