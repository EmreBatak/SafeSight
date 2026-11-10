from PySide6.QtCore import QDateTime, Qt, QTimer, Slot
from PySide6.QtGui import QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from station.ui.messages import View, message
from station.worker import CameraWorker

STATION_NAME = "Giriş A · SafeSight istasyonu"
# tone -> (background, text); the same colour ramps as the screen design
TONES = {
    "neutral": ("#F1EFE8", "#2C2C2A"),
    "accent": ("#E6F1FB", "#0C447C"),
    "warning": ("#FAEEDA", "#633806"),
    "success": ("#EAF3DE", "#27500A"),
    "danger": ("#FCEBEB", "#791F1F"),
}
SYMBOLS = {"warning": "⚠", "success": "✓", "danger": "✕"}
PHOTO_W, PHOTO_H = 96, 116


def keep_space_when_hidden(widget: QWidget) -> None:
    policy = widget.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    widget.setSizePolicy(policy)


class MainWindow(QMainWindow):
    """Station screen: camera on the left; who came, what to do and how far the check is on the right.

    F11 toggles full screen, Esc leaves it.
    """

    def __init__(self, worker: CameraWorker):
        super().__init__()
        self.worker = worker
        self.setWindowTitle("SafeSight")
        self._shown_badge = None
        self._shown_message = None

        self.video = QLabel("Başlatılıyor…")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video.setStyleSheet("background: black; color: white; font-size: 24px; border-radius: 8px;")

        side = QVBoxLayout()
        side.setSpacing(12)
        side.addWidget(self._build_worker_card())
        side.addWidget(self._build_status(), 1)
        side.addWidget(self._build_meter())

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)
        body.addWidget(self.video, 16)
        side_widget = QWidget()
        side_widget.setLayout(side)
        side_widget.setMinimumWidth(340)
        body.addWidget(side_widget, 10)

        central = QWidget()
        central.setLayout(body)
        central.setStyleSheet("background: #F7F6F2;")
        self.setCentralWidget(central)

        self.fps_label = QLabel()
        self.clock = QLabel()
        self.statusBar().addWidget(QLabel(STATION_NAME))
        self.statusBar().addPermanentWidget(self.fps_label)
        self.statusBar().addPermanentWidget(self.clock)
        self.statusBar().setStyleSheet("color: #5F5E5A; font-size: 13px;")
        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)
        self._tick_clock()

        worker.frame_ready.connect(self.show_frame)
        worker.view_changed.connect(self.show_view)
        worker.status.connect(self.show_message)
        worker.failed.connect(self.show_failure)

    def _build_worker_card(self) -> QFrame:
        self.card = QFrame()
        self.card.setStyleSheet("QFrame { background: white; border: 1px solid #E3E1DA; border-radius: 8px; }")
        self.photo = QLabel()
        self.photo.setFixedSize(PHOTO_W, PHOTO_H)
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name = QLabel()
        self.name.setStyleSheet("border: none; font-size: 20px; font-weight: 600; color: #2C2C2A;")
        self.detail = QLabel()
        self.detail.setStyleSheet("border: none; font-size: 14px; color: #5F5E5A;")
        hint = QLabel("Referans fotoğraf")
        hint.setStyleSheet("border: none; font-size: 12px; color: #888780;")
        text = QVBoxLayout()
        text.addStretch()
        text.addWidget(self.name)
        text.addWidget(self.detail)
        text.addWidget(hint)
        text.addStretch()
        row = QHBoxLayout(self.card)
        row.addWidget(self.photo)
        row.addLayout(text, 1)
        keep_space_when_hidden(self.card)
        self.card.hide()
        return self.card

    def _build_status(self) -> QFrame:
        self.status_box = QFrame()
        self.symbol = QLabel()
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        box = QVBoxLayout(self.status_box)
        box.setContentsMargins(20, 20, 20, 20)
        box.addStretch()
        box.addWidget(self.symbol)
        box.addWidget(self.title)
        box.addWidget(self.subtitle)
        box.addStretch()
        return self.status_box

    def _build_meter(self) -> QWidget:
        self.meter = QWidget()
        self.meter_text = QLabel()
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setStyleSheet(
            "QProgressBar { background: #E3E1DA; border: none; border-radius: 5px; }"
            "QProgressBar::chunk { background: #639922; border-radius: 5px; }"
        )
        self.dots = QLabel()
        label = QLabel("Doğru takılı gözlem")
        top = QHBoxLayout()
        top.addWidget(label)
        top.addStretch()
        top.addWidget(self.meter_text)
        col = QVBoxLayout(self.meter)
        col.setContentsMargins(0, 0, 0, 0)
        col.addLayout(top)
        col.addWidget(self.bar)
        col.addWidget(self.dots)
        self.meter.setStyleSheet("font-size: 14px; color: #5F5E5A;")
        keep_space_when_hidden(self.meter)
        self.meter.hide()
        return self.meter

    def _set_status(self, tone: str, title: str, subtitle: str) -> None:
        if self._shown_message == (tone, title, subtitle):
            return  # restyling every frame makes Qt repolish the widgets for nothing
        self._shown_message = (tone, title, subtitle)
        bg, fg = TONES[tone]
        self.status_box.setStyleSheet(f"background: {bg}; border-radius: 8px;")
        self.symbol.setText(SYMBOLS.get(tone, ""))
        self.symbol.setVisible(tone in SYMBOLS)
        self.symbol.setStyleSheet(f"color: {fg}; font-size: 44px;")
        self.title.setText(title)
        self.title.setStyleSheet(f"color: {fg}; font-size: 34px; font-weight: 600;")
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(f"color: {fg}; font-size: 18px;")

    def _show_worker(self, worker) -> None:
        badge = worker.badge_no if worker else None
        if badge == self._shown_badge:
            return
        self._shown_badge = badge
        self.card.setVisible(worker is not None)
        if worker is None:
            return
        self.name.setText(worker.name)
        self.detail.setText(" · ".join(p for p in (worker.department, f"Kart {worker.badge_no}") if p))
        pixmap = QPixmap(str(worker.photo)) if worker.photo and worker.photo.exists() else QPixmap()
        if pixmap.isNull():
            self.photo.setPixmap(QPixmap())
            self.photo.setText(worker.initials)
            self.photo.setStyleSheet(
                "background: #E6F1FB; color: #0C447C; border: none; border-radius: 6px; font-size: 26px; font-weight: 600;"
            )
        else:
            self.photo.setStyleSheet("border: none; border-radius: 6px;")
            self.photo.setPixmap(
                pixmap.scaled(
                    PHOTO_W, PHOTO_H, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )

    @Slot(object)
    def show_view(self, view: View) -> None:
        self._set_status(*message(view))
        self._show_worker(view.worker)
        self.meter.setVisible(view.worker is not None)
        self.bar.setMaximum(view.window)
        self.bar.setValue(view.proper)
        self.meter_text.setText(f"{view.proper} / {view.window}")
        filled = min(view.attempt, view.attempts)
        dots = " ".join("●" if i < filled else "○" for i in range(view.attempts))
        self.dots.setText(f'Deneme {filled}/{view.attempts}  <span style="font-size: 22px;">{dots}</span>')

    @Slot(QImage, float)
    def show_frame(self, image: QImage, fps: float) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video.setPixmap(pixmap)
        self.fps_label.setText(f"{fps:.1f} FPS")

    @Slot(str)
    def show_message(self, text: str) -> None:
        self.video.setText(text)
        self._set_status("neutral", text, "")

    @Slot(str)
    def show_failure(self, text: str) -> None:
        self.video.setText(text)
        self._set_status("danger", "İstasyon çalışmıyor", text)

    def _tick_clock(self) -> None:
        self.clock.setText(QDateTime.currentDateTime().toString("HH:mm"))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.worker.requestInterruption()
        self.worker.wait(3000)
        super().closeEvent(event)
