"""Crops `without_mask` faces from the Kaggle Face Mask Detection dataset into YOLO `no_mask` samples.

Only `without_mask` faces are used (CLAUDE.md §6.1). Most source images also contain masked faces,
and an unlabeled face would be learned as background, so each face is cropped with some margin and
crops that touch any other annotated face are skipped.

Usage:
    python scripts/convert_kaggle_voc_to_yolo.py \
        --src data/raw/kaggle/extracted --out data/prepared/kaggle_no_mask
"""

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import cv2

NO_MASK = 2  # class ids: 0 mask_proper, 1 mask_improper, 2 no_mask


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def w(self) -> int:
        return self.x2 - self.x1

    @property
    def h(self) -> int:
        return self.y2 - self.y1

    def intersects(self, other: "Box") -> bool:
        return self.x1 < other.x2 and other.x1 < self.x2 and self.y1 < other.y2 and other.y1 < self.y2


def read_voc(path: Path) -> tuple[str, list[tuple[str, Box]]]:
    """Returns the image filename and its (label, box) list."""
    root = ET.parse(path).getroot()
    objects = []
    for obj in root.iter("object"):
        bb = obj.find("bndbox")
        box = Box(*(int(float(bb.findtext(k))) for k in ("xmin", "ymin", "xmax", "ymax")))
        objects.append((obj.findtext("name"), box))
    return root.findtext("filename"), objects


def crop_around(face: Box, margin: float, img_w: int, img_h: int) -> Box:
    """Expands the face box by `margin` times its size on each side, clamped to the image."""
    mx, my = round(face.w * margin), round(face.h * margin)
    return Box(max(0, face.x1 - mx), max(0, face.y1 - my), min(img_w, face.x2 + mx), min(img_h, face.y2 + my))


def yolo_label(face: Box, crop: Box) -> str:
    """YOLO line for the face, in coordinates normalized to the crop."""
    cx = (face.x1 + face.x2) / 2 - crop.x1
    cy = (face.y1 + face.y2) / 2 - crop.y1
    return f"{NO_MASK} {cx / crop.w:.6f} {cy / crop.h:.6f} {face.w / crop.w:.6f} {face.h / crop.h:.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, required=True, help="folder with annotations/ and images/")
    parser.add_argument("--out", type=Path, required=True, help="output folder; images/ and labels/ go here")
    parser.add_argument("--min-size", type=int, default=24, help="skip faces smaller than this many pixels")
    parser.add_argument("--margin", type=float, default=1.0, help="crop margin per side, as a multiple of face size")
    args = parser.parse_args()

    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "labels").mkdir(parents=True, exist_ok=True)

    kept = too_small = overlaps = 0
    for xml_path in sorted((args.src / "annotations").glob("*.xml")):
        filename, objects = read_voc(xml_path)
        faces = [box for label, box in objects if label == "without_mask"]
        if not faces:
            continue
        image = cv2.imread(str(args.src / "images" / filename))
        img_h, img_w = image.shape[:2]

        for i, face in enumerate(faces):
            if min(face.w, face.h) < args.min_size:
                too_small += 1
                continue
            crop = crop_around(face, args.margin, img_w, img_h)
            if any(box != face and box.intersects(crop) for _, box in objects):
                overlaps += 1
                continue

            name = f"kaggle_{Path(filename).stem}_{i}"
            cv2.imwrite(str(args.out / "images" / f"{name}.png"), image[crop.y1 : crop.y2, crop.x1 : crop.x2])
            (args.out / "labels" / f"{name}.txt").write_text(yolo_label(face, crop) + "\n")
            kept += 1

    print(f"kept {kept}, too small {too_small}, touching another face {overlaps}")


if __name__ == "__main__":
    main()
