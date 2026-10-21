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

## Run the station app

```powershell
python -m station
```

Options: `--source 1` (another webcam) or `--source path/to/video.mp4` (a looping video instead of a webcam),
`--model models/best.pt` (trained weights), `--fullscreen`.
F11 toggles full screen, Esc leaves it.
The first run downloads the pretrained `yolo11n.pt` (not committed).

## Tests

```powershell
pytest
```
