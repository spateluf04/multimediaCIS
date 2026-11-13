"""Build the reference clips from sources.json.

Downloads each Freesound preview into raw/ (not committed), trims it with
ffmpeg to 16 kHz mono WAV peaking at -1 dBFS, then writes clips.json and
../CREDITS.md.

    python build_clips.py            build everything
    python build_clips.py --suggest  print the loudest window in each source
"""

from __future__ import annotations

import argparse
import array
import json
import math
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAMPLE_RATE = 16000
DEFAULT_DURATION = 4.0
PEAK_DB = -1.0
LICENSE = "CC0 1.0"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"


def ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        sys.exit("ffmpeg not found on PATH")
    return path


def page_url(src: dict) -> str:
    return f"https://freesound.org/people/{src['owner']}/sounds/{src['freesound_id']}/"


def download(src: dict) -> Path:
    out = RAW / f"{src['freesound_id']}.mp3"
    if out.exists():
        return out
    RAW.mkdir(exist_ok=True)
    req = urllib.request.Request(page_url(src), headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    if "publicdomain/zero/1.0" not in page:
        sys.exit(f"{src['id']}: source is no longer CC0, check {page_url(src)}")
    preview = re.search(r'data-mp3="([^"]+)"', page).group(1)
    req = urllib.request.Request(preview, headers={"User-Agent": "Mozilla/5.0"})
    out.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return out


def decode(path: Path) -> array.array:
    cmd = [ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-f", "s16le", "-"]
    samples = array.array("h")
    samples.frombytes(subprocess.run(cmd, capture_output=True, check=True).stdout)
    return samples


def loudest_window(samples: array.array, seconds: float, step: float = 0.25) -> tuple[float, float]:
    """Return (start, rms) of the loudest window of the given length."""
    size, hop = int(seconds * SAMPLE_RATE), int(step * SAMPLE_RATE)
    if len(samples) <= size:
        return 0.0, 0.0
    squares = [0]
    for s in samples:
        squares.append(squares[-1] + s * s)
    best = max(range(0, len(samples) - size, hop), key=lambda i: squares[i + size] - squares[i])
    rms = math.sqrt((squares[best + size] - squares[best]) / size)
    return best / SAMPLE_RATE, rms


def peak_gain_db(raw: Path, start: float, duration: float) -> float:
    """Gain that brings the excerpt's peak to PEAK_DB."""
    samples = decode(raw)
    first = int(start * SAMPLE_RATE)
    segment = samples[first:first + int(duration * SAMPLE_RATE)]
    peak = max((abs(s) for s in segment), default=0)
    if peak == 0:
        sys.exit(f"{raw.name}: excerpt is silent")
    return PEAK_DB - 20 * math.log10(peak / 32768)


def trim(src: dict, raw: Path) -> Path:
    out = HERE / f"{src['id']}.wav"
    duration = src.get("duration", DEFAULT_DURATION)
    gain = peak_gain_db(raw, src["start"], duration)
    cmd = [ffmpeg(), "-v", "error", "-y", "-i", str(raw), "-ss", str(src["start"]),
           "-t", str(duration), "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-af", f"volume={gain:.2f}dB", str(out)]
    subprocess.run(cmd, check=True)
    return out


def clip_entry(src: dict) -> dict:
    return {
        "id": src["id"],
        "sound_type": src["id"].rsplit("_", 1)[0],
        "file": f"clips/{src['id']}.wav",
        "owner": src["owner"],
        "source_url": page_url(src),
        "license": LICENSE,
        "notes": src["notes"],
    }


def credits(sources: list[dict]) -> str:
    lines = [
        "# Media Credits",
        "",
        "## Reference audio clips",
        "",
        "All clips come from [Freesound](https://freesound.org) and are released under "
        f"[CC0 1.0]({LICENSE_URL}). Credit is not required by the license, but we list every "
        "owner here. Each clip is a 4-5 second excerpt of the owner's preview, converted to "
        "16 kHz mono WAV and peak normalized.",
        "",
        "| Clip | Sound | Owner | Original title | Source | License |",
        "|---|---|---|---|---|---|",
    ]
    for src in sources:
        e = clip_entry(src)
        title = src["title"].replace("|", "/")
        lines.append(
            f"| `{e['id']}.wav` | {e['sound_type']} | {e['owner']} | {title} | "
            f"[freesound.org/s/{src['freesound_id']}]({e['source_url']}) | {LICENSE} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suggest", action="store_true")
    args = parser.parse_args()
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))

    if args.suggest:
        for src in sources:
            samples = decode(download(src))
            length = len(samples) / SAMPLE_RATE
            start, rms = loudest_window(samples, src.get("duration", DEFAULT_DURATION))
            print(f"{src['id']:<13} length {length:6.1f}s  loudest at {start:6.2f}s  rms {rms:7.0f}")
        return

    for src in sources:
        trim(src, download(src))
        print(f"built {src['id']}.wav")
    entries = [clip_entry(s) for s in sources]
    (HERE / "clips.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    (HERE.parent / "CREDITS.md").write_text(credits(sources), encoding="utf-8")
    print(f"wrote clips.json and CREDITS.md ({len(entries)} clips)")


if __name__ == "__main__":
    main()
