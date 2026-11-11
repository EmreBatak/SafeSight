import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from station.reporter import Reporter
from station.ui.main_window import MainWindow
from station.worker import CameraWorker
from station.workers import load_workers

ROOT = Path(__file__).resolve().parents[2]
# Trained 3-class mask model (mask_proper, mask_improper, no_mask); not committed, see README.
DEFAULT_MODEL = ROOT / "models" / "mask_n95_v3.pt"
# Card -> worker list; personal data, not committed (see data/workers.example.csv).
DEFAULT_WORKERS = ROOT / "data" / "workers.csv"
# 2-class hard hat model (helmet, no_helmet); release helmet-v1, see README.
DEFAULT_HELMET_MODEL = ROOT / "models" / "helmet_v1.pt"


def parse_source(value: str) -> int | str:
    """'0', '1', ... mean a webcam index; anything else is a video file path."""
    return int(value) if value.isdigit() else value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m station", description="SafeSight check station app")
    parser.add_argument(
        "--source", type=parse_source, default=0, help="webcam index or video file path (default: 0)"
    )
    parser.add_argument(
        "--model", default=str(DEFAULT_MODEL), help="YOLO weights (default: models/mask_n95_v3.pt)"
    )
    parser.add_argument(
        "--helmet-model",
        default=str(DEFAULT_HELMET_MODEL),
        help="hard hat weights; 'none' = check the mask only (default: models/helmet_v1.pt)",
    )
    parser.add_argument("--conf", type=float, default=0.5, help="minimum detection confidence to draw")
    parser.add_argument("--fullscreen", action="store_true", help="start in full screen (kiosk)")
    parser.add_argument(
        "--max-fps", type=float, default=10.0, help="run the model at most this often per second; 0 = no limit (default: 10)"
    )
    parser.add_argument(
        "--workers", type=Path, default=DEFAULT_WORKERS, help="CSV of cards and workers (default: data/workers.csv)"
    )
    parser.add_argument("--width", type=int, default=1280, help="requested webcam width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="requested webcam height (default: 720)")
    parser.add_argument(
        "--api", default="http://127.0.0.1:8000", help="API that stores checks; 'none' = do not save (default: http://127.0.0.1:8000)"
    )
    parser.add_argument("--station", default="Giriş A", help="station name saved with each check (default: Giriş A)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers.exists():
        workers = load_workers(args.workers)
    else:
        print(f"Çalışan listesi bulunamadı: {args.workers} - her kart 'tanınmadı' görünecek.", file=sys.stderr)
        workers = {}
    app = QApplication(sys.argv[:1])
    helmet_model = None if args.helmet_model.lower() == "none" else args.helmet_model
    if helmet_model and not Path(helmet_model).exists():
        print(f"Kask modeli bulunamadı: {helmet_model} - sadece maske kontrol edilecek.", file=sys.stderr)
        helmet_model = None
    reporter = None
    if args.api.lower() != "none":
        reporter = Reporter(args.api, args.station, ROOT / "snapshots" / "unsent")

    worker = CameraWorker(
        source=args.source,
        model_path=args.model,
        conf=args.conf,
        max_fps=args.max_fps,
        workers=workers,
        width=args.width,
        height=args.height,
        reporter=reporter,
        helmet_model_path=helmet_model,
    )
    window = MainWindow(worker)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.resize(1024, 700)
        window.show()

    worker.start()
    return app.exec()
