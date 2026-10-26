"""Auto-labels the Mendeley N95 images with face boxes from the YuNet face detector.

Mendeley labels are per folder (CLAUDE.md §6.1): `Correct/N95` -> `mask_proper`, `Incorrect/N95` ->
`mask_improper`. The box covers the face, as in every dataset. Each image should show one person,
so the largest face is kept; images with no face, or with a second face of similar size, are skipped.

Usage:
    python scripts/autolabel_mendeley_n95.py \
        --src "data/raw/mendeley/n95/NewFace Mask Dataset" --out data/prepared/mendeley_n95 \
        --model models/face/face_detection_yunet_2023mar.onnx [--limit 50 --preview previews/]
"""

import argparse
import random
import shutil
from pathlib import Path

import cv2

CLASSES = {"Correct": 0, "Incorrect": 1}  # class ids: 0 mask_proper, 1 mask_improper, 2 no_mask
DETECT_SIZE = 640  # longest side the detector sees; faces here are large, so this is plenty


def detect_faces(detector: cv2.FaceDetectorYN, image) -> list[tuple[float, float, float, float, float]]:
    """Returns (x1, y1, x2, y2, score) per face, in original image pixels."""
    h, w = image.shape[:2]
    scale = DETECT_SIZE / max(h, w)
    small = cv2.resize(image, (round(w * scale), round(h * scale)))
    detector.setInputSize((small.shape[1], small.shape[0]))
    _, faces = detector.detect(small)
    if faces is None:
        return []
    return [(x / scale, y / scale, (x + fw) / scale, (y + fh) / scale, s) for x, y, fw, fh, *_, s in faces]


def pick_face(faces, img_w: int, img_h: int, second_ratio: float):
    """The largest face clamped to the image, or None if there is none or another face is about as big."""
    faces = sorted(faces, key=lambda f: (f[2] - f[0]) * (f[3] - f[1]), reverse=True)
    if not faces:
        return None
    area = lambda f: (f[2] - f[0]) * (f[3] - f[1])
    if len(faces) > 1 and area(faces[1]) >= second_ratio * area(faces[0]):
        return None
    x1, y1, x2, y2, _ = faces[0]
    return max(0.0, x1), max(0.0, y1), min(float(img_w), x2), min(float(img_h), y2)


def yolo_label(cls: int, box, img_w: int, img_h: int) -> str:
    x1, y1, x2, y2 = box
    return (
        f"{cls} {(x1 + x2) / 2 / img_w:.6f} {(y1 + y2) / 2 / img_h:.6f} "
        f"{(x2 - x1) / img_w:.6f} {(y2 - y1) / img_h:.6f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, required=True, help="folder with Correct/ and Incorrect/")
    parser.add_argument("--out", type=Path, required=True, help="output folder; images/ and labels/ go here")
    parser.add_argument("--model", type=Path, required=True, help="YuNet .onnx weights")
    parser.add_argument("--score", type=float, default=0.5, help="YuNet score threshold (masks lower scores)")
    parser.add_argument("--second-ratio", type=float, default=0.3, help="skip if 2nd face area >= this x largest")
    parser.add_argument("--limit", type=int, help="random sample of this many images per class (trial run)")
    parser.add_argument("--preview", type=Path, help="also write images with the box drawn here, for checking")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    for sub in ("images", "labels"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
    detector = cv2.FaceDetectorYN.create(str(args.model), "", (DETECT_SIZE, DETECT_SIZE), args.score)
    rng = random.Random(args.seed)

    for folder, cls in CLASSES.items():
        paths = sorted((args.src / folder / "N95").rglob("*.jpg"))
        if args.limit:
            paths = rng.sample(paths, min(args.limit, len(paths)))
        kept = no_face = ambiguous = 0
        for path in paths:
            image = cv2.imread(str(path))
            img_h, img_w = image.shape[:2]
            faces = detect_faces(detector, image)
            box = pick_face(faces, img_w, img_h, args.second_ratio)
            if box is None:
                no_face += not faces
                ambiguous += bool(faces)
                continue

            name = f"mendeley_{folder.lower()}_{path.parent.name.lower()}_{path.stem}"
            shutil.copy(path, args.out / "images" / f"{name}.jpg")
            (args.out / "labels" / f"{name}.txt").write_text(yolo_label(cls, box, img_w, img_h) + "\n")
            if args.preview:
                x1, y1, x2, y2 = map(round, box)
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 6)
                cv2.imwrite(str(args.preview / f"{name}.jpg"), cv2.resize(image, None, fx=0.4, fy=0.4))
            kept += 1
        print(f"{folder}: {len(paths)} images, kept {kept}, no face {no_face}, ambiguous {ambiguous}")


if __name__ == "__main__":
    main()
