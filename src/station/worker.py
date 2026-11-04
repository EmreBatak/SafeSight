import os
import sys
import time

# Torch's OpenMP threads spin on the CPU between frames instead of sleeping, which kept
# ~8 cores busy even when the model ran only 10 times a second. Must be set before torch loads.
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


def open_source(source: int | str) -> cv2.VideoCapture | None:
    """Opens a webcam by index, or a video file by path. Returns None if nothing opens."""
    if isinstance(source, str):
        cap = cv2.VideoCapture(source)
        return cap if cap.isOpened() else None

    # DirectShow opens laptop webcams faster on Windows, but not every OpenCV build
    # can use it by index, so fall back to the default backend.
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(source, backend)
        if cap.isOpened():
            return cap
        cap.release()
    return None


class CameraWorker(QThread):
    """Reads the camera (or a video file) and runs the model off the UI thread.

    Emits annotated frames as QImage so the UI only has to display them.
    """

    frame_ready = Signal(QImage, float)  # annotated frame, smoothed FPS
    status = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        source: int | str,
        model_path: str,
        conf: float,
        max_fps: float = 10.0,
        parent=None,
    ):
        super().__init__(parent)
        self.source = source
        self.model_path = model_path
        self.conf = conf
        self.max_fps = max_fps

    def run(self) -> None:
        self.status.emit("Model yükleniyor…")
        # Imported here so the window opens before torch finishes loading.
        from ultralytics import YOLO

        try:
            model = YOLO(self.model_path)
        except Exception as exc:  # bad path, failed download, corrupt weights
            self.failed.emit(f"Model yüklenemedi: {exc}")
            return

        self.status.emit("Kamera açılıyor…")
        cap = open_source(self.source)
        if cap is None:
            if isinstance(self.source, str):
                self.failed.emit(f"Video açılamadı: {self.source}")
            else:
                self.failed.emit(f"Kamera açılamadı (index {self.source}).")
            return

        is_file = isinstance(self.source, str)
        # The decision rule needs ~15 observations, not every webcam frame, so the
        # model runs at most max_fps times a second and the thread sleeps in between.
        interval = 1.0 / self.max_fps if self.max_fps > 0 else 0.0
        fps = 0.0
        last = time.perf_counter()
        next_start = last
        try:
            while not self.isInterruptionRequested():
                wait = next_start - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                next_start = max(next_start + interval, time.perf_counter())
                ok, frame = cap.read()
                if not ok and is_file:
                    # Loop video files so they can stand in for a webcam during demos.
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if not ok:
                    self.failed.emit("Kameradan görüntü alınamadı.")
                    break

                result = model.predict(frame, conf=self.conf, verbose=False)[0]
                annotated = result.plot()

                now = time.perf_counter()
                instant = 1.0 / max(now - last, 1e-6)
                fps = instant if fps == 0.0 else 0.9 * fps + 0.1 * instant
                last = now

                rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                # copy() detaches the QImage from the numpy buffer before it is reused.
                image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(image, fps)
        finally:
            cap.release()
