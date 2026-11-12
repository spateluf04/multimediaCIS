import pytest

from carsense.reasoning.fact import Fact
from carsense.reasoning.working_memory import WorkingMemory


def test_empty():
    wm = WorkingMemory()
    assert len(wm) == 0
    assert wm.values("sound") == set()
    assert not wm.has("sound", "squealing")
    assert wm.audio_match() is None
    assert wm.facts() == []


def test_assert_and_has():
    wm = WorkingMemory()
    wm.assert_fact(Fact("sound", "grinding"))
    assert wm.has("sound", "grinding")
    assert not wm.has("sound", "squealing")
    assert not wm.has("timing", "grinding")


def test_multi_value():
    wm = WorkingMemory()
    wm.assert_fact(Fact("timing", "starting"))
    wm.assert_fact(Fact("timing", "accelerating"))
    assert wm.values("timing") == {"starting", "accelerating"}


def test_duplicate_fact_stored_once():
    wm = WorkingMemory()
    wm.assert_fact(Fact("sound", "hissing"))
    wm.assert_fact(Fact("sound", "hissing"))
    assert len(wm) == 1


def test_single_select_keeps_both_values():
    wm = WorkingMemory()
    wm.assert_fact(Fact("sound", "hissing"))
    wm.assert_fact(Fact("sound", "humming"))
    assert wm.values("sound") == {"hissing", "humming"}


def test_audio_match():
    wm = WorkingMemory()
    wm.assert_fact(Fact("audio_match", "grinding", "audio", 0.7))
    match = wm.audio_match()
    assert match.value == "grinding"
    assert match.similarity == 0.7


def test_audio_match_picks_highest_similarity():
    wm = WorkingMemory()
    wm.assert_fact(Fact("audio_match", "grinding", "audio", 0.4))
    wm.assert_fact(Fact("audio_match", "squealing", "audio", 0.9))
    assert wm.audio_match().value == "squealing"


def test_facts_sorted():
    wm = WorkingMemory()
    wm.assert_fact(Fact("timing", "braking"))
    wm.assert_fact(Fact("sound", "squealing"))
    assert [f.name for f in wm.facts()] == ["sound", "timing"]


def test_clear():
    wm = WorkingMemory.from_answers({"sound": "clicking"}, {"sound": "clicking", "similarity": 0.5})
    wm.clear()
    assert len(wm) == 0
    assert wm.audio_match() is None


def test_from_answers():
    wm = WorkingMemory.from_answers({
        "sound": "hissing",
        "timing": ["idling"],
        "location": "engine_bay",
        "symptom": ["sweet_smell", "running_hot"],
    })
    assert wm.has("sound", "hissing")
    assert wm.has("location", "engine_bay")
    assert wm.values("symptom") == {"sweet_smell", "running_hot"}
    assert all(f.source == "user" for f in wm.facts())
    assert wm.audio_match() is None


def test_from_answers_skips_empty():
    wm = WorkingMemory.from_answers({"sound": "", "timing": [], "symptom": None, "location": ["", "wheels"]})
    assert len(wm) == 1
    assert wm.has("location", "wheels")


def test_from_answers_with_audio():
    wm = WorkingMemory.from_answers({"sound": "humming"}, {"sound": "humming", "similarity": 0.66})
    match = wm.audio_match()
    assert match.source == "audio"
    assert match.similarity == 0.66
    assert wm.values("sound") == {"humming"}


def test_from_answers_similarity_as_string():
    wm = WorkingMemory.from_answers({}, {"sound": "ticking", "similarity": "0.5"})
    assert wm.audio_match().similarity == 0.5


@pytest.mark.parametrize("audio", [
    {"similarity": 0.5},
    {"sound": "ticking"},
    {"sound": "ticking", "similarity": "high"},
    {"sound": "ticking", "similarity": 1.5},
])
def test_from_answers_bad_audio(audio):
    with pytest.raises(ValueError):
        WorkingMemory.from_answers({}, audio)
