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
`--source http://<phone-ip>:8080/video` uses a phone running the IP Webcam app as the camera.

### Check flow

The station waits for a worker's QR card, shows who it belongs to, then checks the mask with the
rule in CLAUDE.md §3: approved once 12 of the newest 15 observations are `mask_proper` (confidence ≥ 0.7)
and the newest 5 all are. An attempt that is not approved within 30 observations (about 3 s) fails and the
screen says why; three failed attempts reject the check. The rule lives in `src/decision/engine.py`
(`Rules` holds the numbers) and has unit tests. Results are not saved yet: the API and database come later.

Cards are looked up in `data/workers.csv` (personal data, not committed). Copy the format from
`data/workers.example.csv`: `badge_no,name,department,photo`, where `photo` is a reference photo path
relative to the CSV, for example `workers/SS-0001.jpg` in `data/workers/`. Excel's semicolon CSV works too.
Print one card per worker with:

```powershell
python scripts/make_qr_cards.py --workers data/workers.csv --sizes 15 --markers qr --out data/qr/worker_cards.pdf
```

## Helmet model

A separate YOLO11n detects hard hats with two classes, `helmet` and `no_helmet` (box on the head; CLAUDE.md §3).
It is trained on [SHWD](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset) (7,581 images, PASCAL VOC).
Download `VOC2028.zip` from the Google Drive link in that README into `data/raw/shwd/`, unzip it, then:

```powershell
python scripts/convert_shwd_voc_to_yolo.py --src data/raw/shwd/VOC2028 --out data/helmet --yaml data/helmet.yaml
yolo detect train model=yolo11n.pt data=<absolute path>/data/helmet.yaml epochs=30 patience=10 imgsz=640 device=mps name=helmet_v1
```

Try it on the webcam with `yolo predict model=models/helmet_v1.pt source=0 show=True`. The station does not use it yet.

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

## QR placement trial

QR reading needs no training: OpenCV decodes the code directly. What needs testing is which card size and
placement (helmet or chest) the webcam reads from 1–3 m. First print the cards:

```powershell
python scripts/make_qr_cards.py
```

This writes `data/qr/cards.pdf` (not committed): QR and ArUco cards for `SS-0001` at 5, 7, 10 and 15 cm,
one per page. Print at 100%, not "fit to page", and check the 10 cm line on the page. ArUco markers are the
fallback if QR does not read from 3 m. Then run one condition at a time:

```powershell
python scripts/qr_trial.py --placement chest --size 15 --distance 2 --person p01
python scripts/qr_trial.py --marker aruco --placement helmet --size 10 --distance 3 --person p01
```

Space starts a trial; a detector passes if it reads the card within 3 s (`--timeout`). After 10 trials
(`--trials`) the results are appended to `data/qr/trials.csv`; no images are saved. The camera opens at
1280x720 by default, since a 640x480 frame is too small for QR beyond about 1 m.

## Tests

```powershell
pytest
```
