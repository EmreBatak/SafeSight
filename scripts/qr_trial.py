"""Measures how reliably a QR or ArUco card is read at the station (CLAUDE.md §3, QR placement).

One run is one condition: marker type, placement, card size and distance. Stand at the marked
distance with the card on the helmet or chest and press space to start a trial; a detector passes
the trial if it reads the expected id within --timeout seconds. All detectors of the marker type
run on the same frames, so one run also compares them. Space starts the next trial, q or Esc stops.

Only result rows are saved (no images). They are appended to --out with the condition, the camera
resolution actually delivered, and per detector: read or not, seconds to read, ms per frame.

Usage:
    python scripts/qr_trial.py --placement chest --size 15 --distance 3 --person p01
    python scripts/qr_trial.py --marker aruco --placement helmet --size 10 --distance 2 --person p01
"""

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_qr_cards import ARUCO_DICT, aruco_id  # noqa: E402

WINDOW = "SafeSight QR denemesi"
FIELDS = [
    "time", "person", "marker", "placement", "size_cm", "distance_m", "light", "camera",
    "trial", "detector", "read", "seconds", "ms_per_frame", "decoded",
]


def make_detectors(marker: str) -> dict:
    """name -> function(frame) returning [(text, corner points)] for every code it decodes."""
    if marker == "aruco":
        detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), cv2.aruco.DetectorParameters())

        def read_aruco(frame):
            corners, ids, _ = detector.detectMarkers(frame)
            return [] if ids is None else [(str(i), c.reshape(-1, 2)) for i, c in zip(ids.ravel(), corners)]

        return {"aruco_4x4": read_aruco}

    def qr_reader(detector):
        def read(frame):
            text, points, _ = detector.detectAndDecode(frame)
            return [(text, points.reshape(-1, 2))] if text and points is not None else []

        return read

    return {"opencv_qr": qr_reader(cv2.QRCodeDetector()), "opencv_qr_aruco": qr_reader(cv2.QRCodeDetectorAruco())}


def read_codes(detectors: dict, frame) -> dict:
    """Runs every detector on the frame: name -> (codes, milliseconds)."""
    out = {}
    for name, read in detectors.items():
        t0 = time.perf_counter()
        codes = read(frame)
        out[name] = (codes, (time.perf_counter() - t0) * 1000)
    return out


def summarize(rows: list[dict]) -> dict:
    """detector -> (reads, trials, median seconds of the successful reads or None)."""
    summary = {}
    for name in dict.fromkeys(r["detector"] for r in rows):
        mine = [r for r in rows if r["detector"] == name]
        times = [float(r["seconds"]) for r in mine if r["read"]]
        summary[name] = (len(times), len(mine), statistics.median(times) if times else None)
    return summary


def open_camera(source: str, width: int, height: int) -> cv2.VideoCapture:
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src, cv2.CAP_DSHOW) if isinstance(src, int) and sys.platform == "win32" else cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def put_lines(view, lines) -> None:
    for i, (text, color) in enumerate(lines):
        y = 30 + 28 * i
        cv2.putText(view, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(view, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--marker", choices=["qr", "aruco"], default="qr")
    parser.add_argument("--expect", default="SS-0001", help="worker id on the card (ArUco: its number)")
    parser.add_argument("--placement", choices=["helmet", "chest"], required=True)
    parser.add_argument("--size", type=float, required=True, help="card symbol width in cm")
    parser.add_argument("--distance", type=float, required=True, help="distance to the camera in m")
    parser.add_argument("--person", required=True, help="participant code, not a name (e.g. p01)")
    parser.add_argument("--light", default="", help="optional label, e.g. normal / dim")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=3.0, help="seconds a read may take to count")
    parser.add_argument("--source", default="0", help="webcam index or video file")
    parser.add_argument("--width", type=int, default=1280, help="requested camera width")
    parser.add_argument("--height", type=int, default=720, help="requested camera height")
    parser.add_argument("--out", type=Path, default=Path("data/qr/trials.csv"))
    args = parser.parse_args()

    expected = str(aruco_id(args.expect)) if args.marker == "aruco" else args.expect
    detectors = make_detectors(args.marker)
    cap = open_camera(args.source, args.width, args.height)
    if not cap.isOpened():
        sys.exit(f"Kamera açılamadı: {args.source}")
    camera = f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
    print(f"Kamera çözünürlüğü: {camera} (istenen {args.width}x{args.height})")

    condition = {
        "person": args.person, "marker": args.marker, "placement": args.placement, "size_cm": args.size,
        "distance_m": args.distance, "light": args.light, "camera": camera,
    }
    rows: list[dict] = []
    trial, start = 0, None  # start is the trial's start time while one is running
    found: dict = {}  # detector -> seconds to its first correct read
    cost: dict = {}  # detector -> ms per frame during the trial
    last_text: dict = {}

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            view = frame.copy()
            if start is not None:
                elapsed = time.perf_counter() - start
                for name, (codes, ms) in read_codes(
                    {n: d for n, d in detectors.items() if n not in found}, frame
                ).items():
                    cost.setdefault(name, []).append(ms)
                    for text, pts in codes:
                        last_text[name] = text
                        good = text == expected
                        cv2.polylines(view, [np.int32(pts)], True, (0, 200, 0) if good else (0, 0, 255), 3)
                        if good:
                            found[name] = time.perf_counter() - start
                if len(found) == len(detectors) or elapsed >= args.timeout:
                    for name in detectors:
                        read = name in found and found[name] <= args.timeout
                        rows.append({
                            "time": datetime.now().isoformat(timespec="seconds"), **condition, "trial": trial,
                            "detector": name, "read": read, "seconds": round(found[name], 3) if read else "",
                            "ms_per_frame": round(statistics.mean(cost[name]), 1) if cost.get(name) else "",
                            "decoded": last_text.get(name, ""),
                        })
                    start = None
                    if trial >= args.trials:
                        break

            if start is None:
                status = f"deneme {trial}/{args.trials} bitti - bosluk: sonraki" if trial else "bosluk: denemeyi baslat"
                lines = [(status, (255, 255, 255))]
                for name, (reads, total, med) in summarize(rows).items():
                    med_text = f", medyan {med:.2f} s" if med is not None else ""
                    lines.append((f"{name}: {reads}/{total} okundu{med_text}", (255, 255, 255)))
            else:
                lines = [(f"deneme {trial}/{args.trials}  {elapsed:.1f} s", (0, 0, 255))]
                lines += [(f"{n}: OKUNDU {found[n]:.2f} s" if n in found else f"{n}: ...", (0, 200, 0)) for n in detectors]
            lines.append((f"{args.marker} {args.placement} {args.size:g} cm {args.distance:g} m  kamera {camera}", (200, 200, 200)))
            put_lines(view, lines)
            cv2.imshow(WINDOW, view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and start is None:
                trial += 1
                start, found, cost, last_text = time.perf_counter(), {}, {}, {}
            elif key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        new = not args.out.exists()
        with args.out.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                writer.writeheader()
            writer.writerows(rows)
    for name, (reads, total, med) in summarize(rows).items():
        med_text = f", median {med:.2f} s" if med is not None else ""
        print(f"{name}: read {reads}/{total}{med_text}")
    print(f"{len(rows)} rows -> {args.out}" if rows else "no finished trials, nothing saved")


if __name__ == "__main__":
    main()
