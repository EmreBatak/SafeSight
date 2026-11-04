from station.app import parse_args, parse_source


def test_digits_are_webcam_indexes():
    assert parse_source("0") == 0
    assert parse_source("2") == 2


def test_other_values_are_file_paths():
    assert parse_source("videos/demo.mp4") == "videos/demo.mp4"


def test_default_source_is_first_webcam():
    assert parse_args([]).source == 0


def test_model_rate_is_limited_by_default():
    assert parse_args([]).max_fps == 10.0
