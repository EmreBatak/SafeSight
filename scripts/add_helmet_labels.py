"""Adds helmet labels to own frames recorded before the helmet check (CLAUDE.md §3, §6.2).

In those sessions nobody wore a helmet, so the class is known (--cls, normally no_helmet); only the
head box is missing. The helmet model draws it: the detected head around the face from labels/ is
taken, whatever class the model gives it. Labels go to helmet_labels/ next to labels/ (0 helmet,
1 no_helmet). Existing helmet labels are left alone. Frames where the model gives the head the other
class with high confidence are listed, so they can be checked by eye.

Usage:
    python scripts/add_helmet_labels.py --helmet-model models/helmet_v1.pt --cls no_helmet \\
        data/own/edaalemreli data/own/yunus data/own/emre
"""

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autolabel_mendeley_n95 import yolo_label  # noqa: E402
from capture_webcam import HELMET_NAMES, pick_head  # noqa: E402


def face_box(label: Path, img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """The face box of a one-line YOLO label, in pixels."""
    _, cx, cy, w, h = map(float, label.read_text().split()[:5])
    return (cx - w / 2) * img_w, (cy - h / 2) * img_h, (cx + w / 2) * img_w, (cy + h / 2) * img_h


def find_image(folder: Path, stem: str) -> Path | None:
    for base in (folder / "images", folder):  # older sessions kept the images next to labels/
        for ext in (".jpg", ".png"):
            if (base / f"{stem}{ext}").exists():
                return base / f"{stem}{ext}"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", type=Path, nargs="+", help="data/own/<person> folders")
    parser.add_argument("--helmet-model", type=Path, required=True)
    parser.add_argument("--cls", choices=HELMET_NAMES, required=True, help="what everyone wore in these frames")
    parser.add_argument("--conf", type=float, default=0.25, help="min confidence for the head box")
    parser.add_argument("--doubt", type=float, default=0.6, help="list frames where the model says the other class above this")
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(args.helmet_model))
    cls = HELMET_NAMES.index(args.cls)
    for folder in args.folders:
        out = folder / "helmet_labels"
        out.mkdir(exist_ok=True)
        written = kept = no_head = 0
        doubts = []
        for label in sorted((folder / "labels").glob("own_*.txt")):
            if (out / label.name).exists():
                kept += 1
                continue
            image_path = find_image(folder, label.stem)
            if image_path is None:
                continue
            image = cv2.imread(str(image_path))
            img_h, img_w = image.shape[:2]
            result = model.predict(image, conf=args.conf, agnostic_nms=True, verbose=False)[0]
            boxes = result.boxes.xyxy.tolist()
            head = pick_head(boxes, face_box(label, img_w, img_h))
            if head is None:
                no_head += 1
                continue
            i = boxes.index(list(head))
            said, conf = int(result.boxes.cls[i]), float(result.boxes.conf[i])
            if said != cls and conf >= args.doubt:
                doubts.append(f"{label.stem} (model: {HELMET_NAMES[said]} {conf:.2f})")
            (out / label.name).write_text(yolo_label(cls, head, img_w, img_h) + "\n")
            written += 1
        print(f"{folder.name}: {written} written as {args.cls}, {kept} already there, no head found {no_head}")
        for doubt in doubts:
            print(f"  check: {doubt}")


if __name__ == "__main__":
    main()
