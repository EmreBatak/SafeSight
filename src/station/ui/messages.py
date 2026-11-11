"""What the station screen says in each state. No Qt here, so the wording is testable."""

from dataclasses import dataclass
from typing import Any

from decision import Check, State
from decision.engine import IMPROPER, MULTIPLE, NO_FACE, NO_HELMET, NO_MASK


@dataclass(frozen=True)
class View:
    """Everything the screen shows, sent from the camera thread once per frame."""

    state: State
    worker: Any = None  # station.workers.Worker or None
    attempt: int = 0
    attempts: int = 3
    proper: int = 0  # mask_proper observations in the current window
    window: int = 15
    reason: str = ""  # why the last attempt failed
    last_seen: str = ""  # the newest observation, for hints while scanning
    result: Check | None = None
    helmet_check: bool = False  # whether the station also checks the hard hat


RETRY = {
    IMPROPER: ("Maskeni düzelt", "Maske burnunu ve ağzını tam kapatmalı."),
    NO_MASK: ("Maskeni tak", "Geçmeden önce toz maskeni tak."),
    NO_HELMET: ("Kaskını tak", "Geçmeden önce baretini tak."),
    NO_FACE: ("Yüzün görünmüyor", "Kameraya dön ve birkaç saniye bekle."),
    MULTIPLE: ("Tek kişi olmalı", "Kamera önünde yalnızca sen dur."),
}
SCAN_HINT = {NO_FACE: RETRY[NO_FACE][1], MULTIPLE: RETRY[MULTIPLE][1], NO_HELMET: RETRY[NO_HELMET][1]}


def message(view: View) -> tuple[str, str, str]:
    """(tone, title, subtitle). Tones: neutral, accent, warning, success, danger."""
    if view.state is State.IDLE:
        return "neutral", "Kartını göster", "Göğsündeki QR kartı kameraya doğru tut."
    if view.state is State.UNKNOWN_CARD:
        return "warning", "Kart tanınmadı", "Bu kart kayıtlı değil. İSG sorumlusuna başvur."
    if view.state is State.SCANNING:
        title = "Maske ve kask kontrol ediliyor…" if view.helmet_check else "Maske kontrol ediliyor…"
        return "accent", title, SCAN_HINT.get(view.last_seen, "Kameraya bak ve birkaç saniye bekle.")
    if view.state is State.RETRY:
        return ("warning", *RETRY.get(view.reason, RETRY[IMPROPER]))
    if view.state is State.APPROVED:
        worn = "Maske ve kask doğru takılı." if view.helmet_check else "Maske doğru takılı."
        return "success", "Geçebilirsin", f"{worn} İyi çalışmalar."
    return "danger", "Geçiş onaylanmadı", "Kaydın İSG sorumlusuna iletildi. Sorumluyla görüş."
