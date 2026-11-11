import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_shwd_voc_to_yolo.py"


def voc(name: str, objects: list[tuple[str, tuple[int, int, int, int]]], w=200, h=100) -> str:
    objs = "".join(
        f"<object><name>{label}</name><bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin><xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object>"
        for label, (x1, y1, x2, y2) in objects
    )
    return f"<annotation><filename>{name}.jpg</filename><size><width>{w}</width><height>{h}</height></size>{objs}</annotation>"


def make_voc(root: Path, samples: dict[str, list], trainval: list[str], test: list[str]) -> None:
    for sub in ("Annotations", "JPEGImages", "ImageSets/Main"):
        (root / sub).mkdir(parents=True)
    for name, objects in samples.items():
        (root / "Annotations" / f"{name}.xml").write_text(voc(name, objects))
        cv2.imwrite(str(root / "JPEGImages" / f"{name}.jpg"), np.zeros((100, 200, 3), np.uint8))
    (root / "ImageSets/Main/trainval.txt").write_text("\n".join(trainval))
    (root / "ImageSets/Main/test.txt").write_text("\n".join(test))


def test_converts_hat_and_person_and_keeps_split(tmp_path):
    src = tmp_path / "VOC2028"
    make_voc(
        src,
        {
            "000001": [("hat", (0, 0, 100, 50)), ("person", (100, 50, 200, 100))],
            "000002": [("person", (50, 25, 150, 75))],
            "000003": [("hat", (0, 0, 10, 10)), ("dog", (20, 20, 40, 40))],  # unknown label: skipped
        },
        trainval=["000001", "000003"],
        test=["000002"],
    )
    out, yaml = tmp_path / "helmet", tmp_path / "helmet.yaml"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--yaml", str(yaml)],
        capture_output=True, text=True, check=True,
    )
    assert (out / "labels/train/shwd_000001.txt").read_text().splitlines() == [
        "0 0.250000 0.250000 0.500000 0.500000",
        "1 0.750000 0.750000 0.500000 0.500000",
    ]
    assert (out / "labels/val/shwd_000002.txt").read_text() == "1 0.500000 0.500000 0.500000 0.500000\n"
    assert not (out / "labels/train/shwd_000003.txt").exists()
    assert "skipped 1: other label: dog" in result.stdout
    assert "train: helmet/images/train" in yaml.read_text()
    assert "1: no_helmet" in yaml.read_text()
