import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "convert_kaggle", Path(__file__).parents[1] / "scripts" / "convert_kaggle_voc_to_yolo.py"
)
convert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(convert)
Box = convert.Box


def test_crop_adds_margin_on_each_side():
    assert convert.crop_around(Box(100, 100, 120, 130), 1.0, 640, 480) == Box(80, 70, 140, 160)


def test_crop_is_clamped_to_image():
    assert convert.crop_around(Box(5, 5, 25, 25), 1.0, 30, 30) == Box(0, 0, 30, 30)


def test_label_is_normalized_to_crop():
    face, crop = Box(80, 70, 100, 90), Box(60, 50, 120, 110)
    assert convert.yolo_label(face, crop) == "2 0.500000 0.500000 0.333333 0.333333"


def test_touching_boxes_do_not_intersect():
    assert not Box(0, 0, 10, 10).intersects(Box(10, 0, 20, 10))
    assert Box(0, 0, 10, 10).intersects(Box(9, 9, 20, 20))
