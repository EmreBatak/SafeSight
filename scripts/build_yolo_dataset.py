"""Merges the prepared public datasets into data/yolo/{images,labels}/{train,val} and writes data/data.yaml.

Public data has no person ids (CLAUDE.md §6.2), so the split is by group instead of by image:
Mendeley photos are burst shots with consecutive numbers, so blocks of `--block` numbers stay
together; Kaggle crops stay with their source image. This keeps near-duplicate frames out of val.
`no_mask` is far smaller than the other classes, so its train images are repeated `--oversample`
times; this happens after the split and only in train.

Usage:
    python scripts/build_yolo_dataset.py --prepared data/prepared --out data/yolo --yaml data/data.yaml
"""

import argparse
import os
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

NAMES = ["mask_proper", "mask_improper", "no_mask"]


def group_key(stem: str, block: int) -> str:
    """mendeley_correct_male_FM 7850 -> mendeley_correct_male_78 ; kaggle_maksssksksss12_0 -> kaggle_maksssksksss12"""
    if stem.startswith("mendeley_"):
        prefix, number = re.match(r"(mendeley_[a-z]+_[a-z]+)_\D*(\d+)", stem).groups()
        return f"{prefix}_{int(number) // block}"
    return stem.rsplit("_", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prepared", type=Path, required=True, help="folder of datasets, each with images/ labels/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--yaml", type=Path, required=True)
    parser.add_argument("--val", type=float, default=0.15, help="fraction of groups for val")
    parser.add_argument("--block", type=int, default=100, help="Mendeley file numbers per group")
    parser.add_argument("--oversample", type=int, default=5, help="repeat no_mask train images this many times")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    groups = defaultdict(list)
    for label in sorted(args.prepared.glob("*/labels/*.txt")):
        image = next(label.parents[1].joinpath("images").glob(f"{glob_escape(label.stem)}.*"))
        groups[group_key(label.stem, args.block)].append((image, label))

    keys = sorted(groups)
    random.Random(args.seed).shuffle(keys)
    val_keys = set(keys[: round(len(keys) * args.val)])

    if args.out.exists():
        shutil.rmtree(args.out)
    counts = defaultdict(lambda: [0, 0, 0])
    for key in keys:
        split = "val" if key in val_keys else "train"
        for sub in ("images", "labels"):
            (args.out / sub / split).mkdir(parents=True, exist_ok=True)
        for image, label in groups[key]:
            cls = int(label.read_text().split()[0])
            copies = args.oversample if split == "train" and cls == 2 else 1
            for c in range(copies):
                stem = label.stem if c == 0 else f"{label.stem}_dup{c}"
                shutil.copy(image, args.out / "images" / split / f"{stem}{image.suffix}")
                shutil.copy(label, args.out / "labels" / split / f"{stem}.txt")
                counts[split][cls] += 1

    rel = Path(os.path.relpath(args.out.resolve(), args.yaml.resolve().parent)).as_posix()
    args.yaml.write_text(
        # no `path:` key, so Ultralytics resolves train/val relative to the yaml's folder
        f"train: {rel}/images/train\nval: {rel}/images/val\n"
        "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES))
    )
    for split, c in counts.items():
        print(split, dict(zip(NAMES, c)))


def glob_escape(text: str) -> str:
    return re.sub(r"([*?\[])", r"[\1]", text)


if __name__ == "__main__":
    main()
