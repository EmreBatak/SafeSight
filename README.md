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
F11 toggles full screen, Esc leaves it.
By default it loads the trained mask model `models/mask_n95_v1.pt` (not committed;
copy it from `runs/detect/runs/n95_v1/weights/best.pt` after training).

## Tests

```powershell
pytest
```
