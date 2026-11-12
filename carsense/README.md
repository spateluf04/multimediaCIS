# CarSense

A multimedia expert system that helps drivers figure out what is wrong with their car from the noise it makes. You answer a few questions, compare against reference sounds, optionally record the noise, and get a likely diagnosis with urgency, safety advice, part images and video, a rough cost, and the rules that led to it.

CIS 4930 Multimedia Expert Systems, University of Florida.

**Team:** Dipak Mehta (leader), Edib Music, Kush Patel, Samir Patel, Sheehan Rahman
**Domain expert:** Himal Patel

## Layout

```
backend/        Python backend (Flask controller, inference engine, audio, explanation)
  carsense/     reasoning/, knowledge/, audio/, explanation/
  tests/        pytest tests
kb/             rules.json, parts.json, questions.json
media/          reference clips, part images, videos, CREDITS.md
frontend/       TypeScript UI (Vite)
docs/           core-api.md, the contract between modules
report/         Milestone 3 report, figures, screenshots, logs
```

## Requirements

- Python 3.11 or newer
- ffmpeg (only for preparing the reference clips)
- pandoc (only for building the report)
- Node.js 18+ (frontend, see `frontend/`)

## Backend setup

### Windows (PowerShell)

```powershell
winget install Python.Python.3.11 Gyan.FFmpeg JohnMacFarlane.Pandoc
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### WSL2 / Ubuntu

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv ffmpeg pandoc
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Mac

```bash
brew install python@3.11 ffmpeg pandoc
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the tests

From `backend/` with the venv active:

```
python -m pytest -q
```

## Module contract

See [docs/core-api.md](docs/core-api.md) for fact names, the rule format, and what the inference engine returns.
