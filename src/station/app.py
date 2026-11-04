import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from station.ui.main_window import MainWindow
from station.worker import CameraWorker

# Trained 3-class mask model (mask_proper, mask_improper, no_mask); not committed, see README.
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "mask_n95_v1.pt"


def parse_source(value: str) -> int | str:
    """'0', '1', ... mean a webcam index; anything else is a video file path."""
    return int(value) if value.isdigit() else value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m station", description="SafeSight check station app")
    parser.add_argument(
        "--source", type=parse_source, default=0, help="webcam index or video file path (default: 0)"
    )
    parser.add_argument(
        "--model", default=str(DEFAULT_MODEL), help="YOLO weights (default: models/mask_n95_v1.pt)"
    )
    parser.add_argument("--conf", type=float, default=0.5, help="minimum detection confidence to draw")
    parser.add_argument("--fullscreen", action="store_true", help="start in full screen (kiosk)")
    parser.add_argument(
        "--max-fps", type=float, default=10.0, help="run the model at most this often per second; 0 = no limit (default: 10)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv[:1])

    worker = CameraWorker(
        source=args.source,
        model_path=args.model,
        conf=args.conf,
        max_fps=args.max_fps,
    )
    window = MainWindow(worker)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.resize(1024, 700)
        window.show()

    worker.start()
    return app.exec()
