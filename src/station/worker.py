import os
import sys
import time

# Torch's OpenMP threads spin on the CPU between frames instead of sleeping, which kept
# ~8 cores busy even when the model ran only 10 times a second. Must be set before torch loads.
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from decision import Engine, Rules, State, observe
from decision.engine import IMPROPER, NO_MASK, PROPER
from station.ui.messages import View

BOX_COLORS = {PROPER: (60, 160, 40), IMPROPER: (20, 140, 230), NO_MASK: (50, 50, 220)}  # BGR


def open_source(source: int | str, width: int = 1280, height: int = 720) -> cv2.VideoCapture | None:
    """Opens a webcam by index, or a video file or stream URL. Returns None if nothing opens."""
    if isinstance(source, str):
        cap = cv2.VideoCapture(source)
        return cap if cap.isOpened() else None

    # DirectShow opens laptop webcams faster on Windows, but not every OpenCV build
    # can use it by index, so fall back to the default backend.
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(source, backend)
        if cap.isOpened():
            # Webcams default to 640x480, where a QR card is unreadable beyond about 1 m.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            return cap
        cap.release()
    return None


def draw_boxes(frame: np.ndarray, result, min_conf: float) -> None:
    for box, cls, conf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
        if conf < min_conf:
            continue
        name = result.names[int(cls)]
        color = BOX_COLORS.get(name, (200, 200, 200))
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        label = f"{name} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
        cv2.putText(frame, label, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


class CameraWorker(QThread):
    """Runs the camera, QR reading, the model and the decision engine off the UI thread.

    While the station is idle only the QR detector runs. Once a card is read, the mask model runs
    on every frame and feeds the engine. Each frame the UI gets the image and a View to show.
    """

    frame_ready = Signal(QImage, float)  # annotated frame, smoothed FPS
    view_changed = Signal(object)  # station.ui.messages.View
    status = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        source: int | str,
        model_path: str,
        conf: float,
        max_fps: float = 10.0,
        workers: dict | None = None,
        rules: Rules = Rules(),
        width: int = 1280,
        height: int = 720,
        parent=None,
    ):
        super().__init__(parent)
        self.source = source
        self.model_path = model_path
        self.conf = conf
        self.max_fps = max_fps
        self.workers = workers or {}
        self.rules = rules
        self.width = width
        self.height = height

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
        cap = open_source(self.source, self.width, self.height)
        if cap is None:
            if isinstance(self.source, str):
                self.failed.emit(f"Video açılamadı: {self.source}")
            else:
                self.failed.emit(f"Kamera açılamadı (index {self.source}).")
            return

        engine = Engine(self.rules)
        qr = cv2.QRCodeDetectorAruco()  # read more cards and ran faster than QRCodeDetector in the QR trial
        is_file = isinstance(self.source, str) and "://" not in self.source
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

                now = time.monotonic()
                engine.tick(now)
                annotated = frame.copy()
                seen = ""
                if engine.state is State.IDLE:
                    text, points, _ = qr.detectAndDecode(frame)
                    if text:
                        engine.card(text, self.workers.get(text), now)
                        if points is not None:
                            cv2.polylines(annotated, [np.int32(points).reshape(-1, 2)], True, (60, 160, 40), 4)
                elif engine.state is not State.UNKNOWN_CARD:
                    # agnostic NMS: one box per face, so two classes on one face is not two people
                    result = model.predict(frame, conf=self.conf, agnostic_nms=True, verbose=False)[0]
                    draw_boxes(annotated, result, self.conf)
                    if engine.state is State.SCANNING:
                        detections = [(result.names[int(c)], float(p)) for c, p in zip(result.boxes.cls, result.boxes.conf)]
                        seen = observe(detections, self.rules.min_conf)
                        engine.frame(seen, now)

                self.view_changed.emit(
                    View(
                        state=engine.state,
                        worker=engine.worker,
                        attempt=engine.attempt,
                        attempts=self.rules.attempts,
                        proper=engine.proper_count,
                        window=self.rules.window,
                        reason=engine.reason,
                        last_seen=seen,
                        result=engine.result,
                    )
                )

                now_pc = time.perf_counter()
                instant = 1.0 / max(now_pc - last, 1e-6)
                fps = instant if fps == 0.0 else 0.9 * fps + 0.1 * instant
                last = now_pc

                rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                # copy() detaches the QImage from the numpy buffer before it is reused.
                image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(image, fps)
        finally:
            cap.release()
