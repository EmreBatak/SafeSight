"""Records labeled webcam frames of one person for fine-tuning (CLAUDE.md §6.2).

Press 1 (mask_proper), 2 (mask_improper) or 3 (no_mask) to start recording that class, space to
pause, q or Esc to quit. With --helmet-model, press k to switch between helmet on and off (this pauses
recording, so frames taken while the helmet goes on or off are not saved). The head box then comes
from the helmet model and the class from the k switch; it is written to helmet_labels/ (0 helmet,
1 no_helmet, as in data/helmet.yaml). Frames where the model finds no head get no helmet label. While recording, up to `--rate` frames a second are saved with a YOLO label.
The face box comes from the same YuNet detector and rules as the Mendeley labels
(autolabel_mendeley_n95.py), so frames with no face or with a second face are skipped.

Only record people who gave written consent. Output goes to data/own/<person>/{images,labels},
which stays out of git; pass it to build_yolo_dataset.py like any prepared dataset.

Usage:
    python scripts/capture_webcam.py --person emre --model models/face/face_detection_yunet_2023mar.onnx \
        --helmet-model models/helmet_v1.pt
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autolabel_mendeley_n95 import DETECT_SIZE, detect_faces, pick_face, yolo_label  # noqa: E402

NAMES = ["mask_proper", "mask_improper", "no_mask"]
KEY_NAMES = ["dogru", "yanlis", "maskesiz"]  # on-screen text; OpenCV fonts have no Turkish letters
HELMET_NAMES = ["helmet", "no_helmet"]  # class ids of the helmet model (data/helmet.yaml)
WINDOW = "SafeSight veri kaydi"


def safe_name(person: str) -> str:
    """'Yunus Emre Köybaşı' -> 'yunusemrekoybasi'. No underscores, so it stays one part of the file name."""
    text = person.lower().translate(str.maketrans("çğıöşüâî", "cgiosuai"))
    return "".join(c for c in text if c.isascii() and c.isalnum())


def sample_stem(person: str, session: str, n: int) -> str:
    """build_yolo_dataset.py groups by everything before the last '_', i.e. one group per session."""
    return f"own_{person}_{session}_{n:05d}"


def pick_head(heads, face) -> tuple[float, float, float, float] | None:
    """The detected head box [(x1, y1, x2, y2)] that contains the face centre, the largest if several."""
    cx, cy = (face[0] + face[2]) / 2, (face[1] + face[3]) / 2
    around = [h for h in heads if h[0] <= cx <= h[2] and h[1] <= cy <= h[3]]
    if not around:
        return None
    return max(around, key=lambda h: (h[2] - h[0]) * (h[3] - h[1]))[:4]


def open_camera(source: str) -> cv2.VideoCapture:
    if source.isdigit() and sys.platform == "win32":
        return cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
    return cv2.VideoCapture(int(source) if source.isdigit() else source)


def draw_overlay(
    view, box, recording: int | None, counts: list[int], skipped: int, helmet: int | None = None, head=None,
    helmet_counts: list[int] | None = None,
) -> None:
    if box is not None:
        x1, y1, x2, y2 = map(round, box)
        color = (0, 200, 0) if recording is not None else (0, 200, 255)
        cv2.rectangle(view, (x1, y1), (x2, y2), color, 2)
    if head is not None:
        x1, y1, x2, y2 = map(round, head)
        cv2.rectangle(view, (x1, y1), (x2, y2), (200, 140, 30), 2)
    if recording is None:
        status, color = "DURAKLATILDI", (255, 255, 255)
    else:
        status, color = f"KAYIT: {NAMES[recording]}", (0, 0, 255)
    if box is None:
        status += "  (yuz yok / iki yuz)"
    totals = " | ".join(f"{k} {c}" for k, c in zip(KEY_NAMES, counts)) + f" | atlanan {skipped}"
    lines = [(status, color), (totals, (255, 255, 255))]
    keys = "1 dogru  2 yanlis  3 maskesiz  bosluk dur  q cik"
    if helmet_counts is not None:
        state = "KASK: VAR" if helmet == 0 else "KASK: YOK"
        lines.append((f"{state}   (kask var {helmet_counts[0]} | kask yok {helmet_counts[1]})", (30, 200, 255)))
        keys += "  k kask var/yok"
    lines.append((keys, (200, 200, 200)))
    for i, (text, c) in enumerate(lines):
        y = 30 + 28 * i
        cv2.putText(view, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(view, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--person", required=True, help="who is in front of the camera (one person per run)")
    parser.add_argument("--model", type=Path, required=True, help="YuNet .onnx weights")
    parser.add_argument("--out", type=Path, default=Path("data/own"))
    parser.add_argument("--source", default="0", help="webcam index or video file (default: 0)")
    parser.add_argument("--rate", type=float, default=3.0, help="frames saved per second while recording")
    parser.add_argument("--score", type=float, default=0.5, help="YuNet score threshold (masks lower scores)")
    parser.add_argument("--second-ratio", type=float, default=0.3, help="skip if 2nd face area >= this x largest")
    parser.add_argument("--helmet-model", type=Path, help="helmet YOLO weights; also writes helmet_labels/ (head box)")
    parser.add_argument("--helmet-conf", type=float, default=0.25, help="min confidence for the head box")
    args = parser.parse_args()

    person = safe_name(args.person)
    if not person:
        parser.error("--person needs at least one letter or digit")
    if not args.model.exists():
        parser.error(f"YuNet model not found: {args.model}")
    images, labels = args.out / person / "images", args.out / person / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    helmet_model = helmet_labels = None
    if args.helmet_model:
        if not args.helmet_model.exists():
            parser.error(f"helmet model not found: {args.helmet_model}")
        from ultralytics import YOLO

        helmet_model = YOLO(str(args.helmet_model))
        helmet_labels = args.out / person / "helmet_labels"
        helmet_labels.mkdir(parents=True, exist_ok=True)

    detector = cv2.FaceDetectorYN.create(str(args.model), "", (DETECT_SIZE, DETECT_SIZE), args.score)
    cap = open_camera(args.source)
    if not cap.isOpened():
        sys.exit(f"Kamera açılamadı: {args.source}")

    session = time.strftime("%Y%m%d%H%M%S")
    print(f"Kayıt: {images.parent}  (oturum {session}). Sadece yazılı onam veren kişileri kaydedin.")
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    recording = None
    counts, skipped, saved = [0, 0, 0], 0, 0
    helmet, helmet_counts, no_head = 0, [0, 0], 0  # helmet state set with k; starts as "helmet on"
    last_save = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            img_h, img_w = frame.shape[:2]
            box = pick_face(detect_faces(detector, frame), img_w, img_h, args.second_ratio)
            head = None
            if helmet_model is not None and box is not None:
                result = helmet_model.predict(frame, conf=args.helmet_conf, agnostic_nms=True, verbose=False)[0]
                head = pick_head(result.boxes.xyxy.tolist(), box)

            now = time.monotonic()
            if recording is not None and now - last_save >= 1 / args.rate:
                last_save = now
                if box is None:
                    skipped += 1
                else:
                    stem = sample_stem(person, session, saved)
                    cv2.imwrite(str(images / f"{stem}.jpg"), frame)
                    (labels / f"{stem}.txt").write_text(yolo_label(recording, box, img_w, img_h) + "\n")
                    counts[recording] += 1
                    saved += 1
                    if helmet_labels is not None:
                        if head is None:
                            no_head += 1
                        else:
                            (helmet_labels / f"{stem}.txt").write_text(yolo_label(helmet, head, img_w, img_h) + "\n")
                            helmet_counts[helmet] += 1

            view = frame.copy()  # the saved frame stays free of the overlay
            draw_overlay(
                view, box, recording, counts, skipped, helmet, head, helmet_counts if helmet_model else None
            )
            cv2.imshow(WINDOW, view)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("1"), ord("2"), ord("3")):
                recording = key - ord("1")
            elif key == ord(" "):
                recording = None
            elif key == ord("k") and helmet_model is not None:
                helmet, recording = 1 - helmet, None  # pause while the helmet goes on or off
            elif key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(", ".join(f"{n}: {c}" for n, c in zip(NAMES, counts)) + f", skipped (no face or two faces): {skipped}")
    if helmet_model is not None:
        print(", ".join(f"{n}: {c}" for n, c in zip(HELMET_NAMES, helmet_counts)) + f", no head found: {no_head}")


if __name__ == "__main__":
    main()
