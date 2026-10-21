from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QSizePolicy

from station.worker import CameraWorker


class MainWindow(QMainWindow):
    """Station screen. F11 toggles full screen, Esc leaves it."""

    def __init__(self, worker: CameraWorker):
        super().__init__()
        self.worker = worker
        self.setWindowTitle("SafeSight")

        self.video = QLabel("Başlatılıyor…")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video.setStyleSheet("background: black; color: white; font-size: 24px;")
        self.setCentralWidget(self.video)

        worker.frame_ready.connect(self.show_frame)
        worker.status.connect(self.show_message)
        worker.failed.connect(self.show_message)

    @Slot(QImage, float)
    def show_frame(self, image: QImage, fps: float) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video.setPixmap(pixmap)
        self.statusBar().showMessage(f"{fps:.1f} FPS")

    @Slot(str)
    def show_message(self, text: str) -> None:
        self.video.setText(text)

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
