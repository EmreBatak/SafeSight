# SafeSight

Prototype check station that verifies with a camera whether a mine worker wears a dust mask correctly.
Rejected checks go to a dashboard for human review.
Project context and decisions: [CLAUDE.md](CLAUDE.md).

## Setup (Windows, Python 3.11)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## Setup (macOS, Python 3.11)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On first launch, macOS asks for camera access for the terminal app
(System Settings → Privacy & Security → Camera).

## Run the station app

```powershell
python -m station
```

On macOS, activate the environment first with `source .venv/bin/activate`.

Options: `--source 1` (another webcam) or `--source path/to/video.mp4` (a looping video instead of a webcam),
`--model yolo11n.pt` (pretrained COCO model instead of the mask model), `--fullscreen`.
To keep the laptop cool, the model runs at most 10 times a second; change it with `--max-fps 15`
(`--max-fps 0` removes the limit).
F11 toggles full screen, Esc leaves it.
By default it loads the trained mask model `models/mask_n95_v3.pt` (not committed;
get it with `gh release download model-v3 -D models`).

## Record own training data

One person per run, and only people who gave written consent (CLAUDE.md §6.2):

```powershell
python scripts/capture_webcam.py --person emre --model models/face/face_detection_yunet_2023mar.onnx
```

Press 1 (mask worn correctly), 2 (worn wrongly: nose or chin uncovered) or 3 (no mask) to record that class,
space to pause, q to quit. Change distance (1–3 m), angle and light while recording. Frames are saved
with the YuNet face box to `data/own/<person>/` (not committed); frames with no face or two faces are skipped.
The YuNet weights `face_detection_yunet_2023mar.onnx` come from
[opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet).

## Tests

```powershell
pytest
```
