import importlib.util
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


autolabel = load("autolabel_mendeley_n95")
build = load("build_yolo_dataset")
capture = load("capture_webcam")


def test_largest_face_is_picked_and_clamped():
    faces = [(10, 10, 20, 20, 0.9), (-5, 50, 95, 150, 0.6)]
    assert autolabel.pick_face(faces, 100, 120, 0.3) == (0.0, 50, 95, 120.0)


def test_two_similar_faces_are_ambiguous():
    assert autolabel.pick_face([(0, 0, 10, 10, 0.9), (20, 0, 29, 9, 0.9)], 100, 100, 0.3) is None


def test_no_face():
    assert autolabel.pick_face([], 100, 100, 0.3) is None


def test_label_is_normalized_to_image():
    assert autolabel.yolo_label(1, (20, 10, 60, 50), 100, 200) == "1 0.400000 0.150000 0.400000 0.200000"


def test_mendeley_burst_shots_share_a_group():
    assert build.group_key("mendeley_correct_male_FM 7850", 100) == build.group_key("mendeley_correct_male_FM 7899", 100)
    assert build.group_key("mendeley_correct_male_FM 7850", 100) != build.group_key("mendeley_correct_male_FM 7900", 100)


def test_kaggle_crops_stay_with_source_image():
    assert build.group_key("kaggle_maksssksksss12_0", 100) == build.group_key("kaggle_maksssksksss12_3", 100)


def test_person_name_becomes_one_ascii_word():
    assert capture.safe_name("Yunus Emre Köybaşı") == "yunusemrekoybasi"
    assert capture.safe_name("emre_b-2") == "emreb2"


def test_one_capture_session_is_one_group():
    a = capture.sample_stem("emre", "20261104120000", 0)
    b = capture.sample_stem("emre", "20261104120000", 41)
    later = capture.sample_stem("emre", "20261104130000", 0)
    assert build.group_key(a, 100) == build.group_key(b, 100) != build.group_key(later, 100)
