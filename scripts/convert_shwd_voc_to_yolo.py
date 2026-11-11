"""Converts SHWD (Safety Helmet Wearing Dataset, PASCAL VOC) into a YOLO dataset for the helmet model.

Classes (CLAUDE.md §3): 0 helmet (SHWD `hat`), 1 no_helmet (SHWD `person`, a bare head). Every head
in SHWD is labeled, so whole images are used. Images with any other label are skipped, so nothing
that might be a head stays unlabeled. SHWD's own split is kept: trainval -> train, test -> val.
Images are hard-linked when possible, so the YOLO copy takes no extra disk space.

Usage:
    python scripts/convert_shwd_voc_to_yolo.py --src data/raw/shwd/VOC2028 --out data/helmet --yaml data/helmet.yaml
"""

import argparse
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NAMES = ["helmet", "no_helmet"]
CLASS_OF = {"hat": 0, "person": 1}


def read_voc(path: Path) -> tuple[str, int, int, list[tuple[str, tuple[float, float, float, float]]]]:
    """Returns (image filename, width, height, [(label, (x1, y1, x2, y2))])."""
    root = ET.parse(path).getroot()
    size = root.find("size")
    w = int(float(size.findtext("width"))) if size is not None else 0
    h = int(float(size.findtext("height"))) if size is not None else 0
    objects = []
    for obj in root.iter("object"):
        bb = obj.find("bndbox")
        box = tuple(float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        objects.append(((obj.findtext("name") or "").strip().lower(), box))
    return root.findtext("filename") or f"{path.stem}.jpg", w, h, objects


def yolo_lines(objects, w: int, h: int) -> list[str]:
    lines = []
    for label, (x1, y1, x2, y2) in objects:
        x1, x2 = max(0.0, min(x1, x2)), min(float(w), max(x1, x2))
        y1, y2 = max(0.0, min(y1, y2)), min(float(h), max(y1, y2))
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        lines.append(f"{CLASS_OF[label]} {cx:.6f} {cy:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return lines


def link_or_copy(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, required=True, help="the VOC2028 folder (Annotations/, ImageSets/, JPEGImages/)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--yaml", type=Path, required=True)
    args = parser.parse_args()

    splits = {}
    for name, split in (("trainval", "train"), ("test", "val")):
        ids = (args.src / "ImageSets" / "Main" / f"{name}.txt").read_text().split()
        splits.update({i: split for i in ids})

    if args.out.exists():
        shutil.rmtree(args.out)
    images = Counter()
    boxes = Counter()
    skipped = Counter()
    for image_id, split in sorted(splits.items()):
        xml_path = args.src / "Annotations" / f"{image_id}.xml"
        image_path = args.src / "JPEGImages" / f"{image_id}.jpg"
        if not xml_path.exists() or not image_path.exists():
            skipped["missing file"] += 1
            continue
        _, w, h, objects = read_voc(xml_path)
        other = {label for label, _ in objects} - CLASS_OF.keys()
        if other:
            skipped["other label: " + ",".join(sorted(other))] += 1
            continue
        if not w or not h:
            import cv2

            h, w = cv2.imread(str(image_path)).shape[:2]
        lines = yolo_lines(objects, w, h)
        for sub in ("images", "labels"):
            (args.out / sub / split).mkdir(parents=True, exist_ok=True)
        stem = f"shwd_{image_id}"
        link_or_copy(image_path, args.out / "images" / split / f"{stem}.jpg")
        (args.out / "labels" / split / f"{stem}.txt").write_text("".join(f"{line}\n" for line in lines))
        images[split] += 1
        for line in lines:
            boxes[(split, NAMES[int(line.split()[0])])] += 1

    rel = os.path.relpath(args.out, args.yaml.parent)
    args.yaml.write_text(
        f"# SHWD helmet dataset, made by scripts/convert_shwd_voc_to_yolo.py\n"
        f"# paths are relative to this file's folder; pass this file's absolute path to YOLO\n"
        f"train: {rel}/images/train\nval: {rel}/images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES))
    )
    for split in ("train", "val"):
        print(f"{split}: {images[split]} images, " + ", ".join(f"{n} {boxes[(split, n)]}" for n in NAMES))
    for reason, n in skipped.most_common():
        print(f"skipped {n}: {reason}")


if __name__ == "__main__":
    main()
