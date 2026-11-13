import json
import wave

import pytest
from conftest import KB_DIR, REPO_ROOT

from carsense.knowledge.knowledge_base import KnowledgeBase

MEDIA = REPO_ROOT / "media"
CLIPS = json.loads((MEDIA / "clips" / "clips.json").read_text(encoding="utf-8"))


def test_three_clips_per_sound():
    sounds = KnowledgeBase.load(KB_DIR).options("sound")
    counts = {s: 0 for s in sounds}
    for clip in CLIPS:
        counts[clip["sound_type"]] += 1
    assert counts == {s: 3 for s in sounds}


def test_ids_unique_and_match_files():
    assert len({c["id"] for c in CLIPS}) == len(CLIPS)
    for clip in CLIPS:
        assert clip["file"] == f"clips/{clip['id']}.wav"


def test_every_clip_credited():
    credits = (MEDIA / "CREDITS.md").read_text(encoding="utf-8")
    for clip in CLIPS:
        assert clip["owner"]
        assert clip["source_url"].startswith("https://freesound.org/people/")
        assert clip["license"] == "CC0 1.0"
        assert f"`{clip['id']}.wav`" in credits


@pytest.mark.parametrize("clip", CLIPS, ids=[c["id"] for c in CLIPS])
def test_wav_format(clip):
    with wave.open(str(MEDIA / clip["file"])) as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert 3.0 <= w.getnframes() / w.getframerate() <= 5.0
