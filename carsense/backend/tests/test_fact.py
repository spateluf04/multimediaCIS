from dataclasses import FrozenInstanceError

import pytest

from carsense.reasoning.fact import Fact


def test_user_fact_defaults():
    f = Fact("sound", "squealing")
    assert f.name == "sound"
    assert f.value == "squealing"
    assert f.source == "user"
    assert f.similarity is None


def test_audio_fact_with_similarity():
    f = Fact("audio_match", "grinding", source="audio", similarity=0.82)
    assert f.source == "audio"
    assert f.similarity == 0.82


def test_audio_fact_without_similarity():
    assert Fact("audio_match", "humming", source="audio").similarity is None


@pytest.mark.parametrize("sim", [0.0, 1.0])
def test_similarity_bounds_allowed(sim):
    assert Fact("audio_match", "hissing", "audio", sim).similarity == sim


def test_frozen():
    f = Fact("sound", "squealing")
    with pytest.raises(FrozenInstanceError):
        f.value = "grinding"


def test_equal_facts_hash_the_same():
    a = Fact("timing", "braking")
    b = Fact("timing", "braking")
    assert a == b
    assert len({a, b}) == 1


def test_source_matters_for_equality():
    assert Fact("sound", "squealing") != Fact("sound", "squealing", "audio")


@pytest.mark.parametrize("name, value", [("", "squealing"), ("sound", "")])
def test_empty_name_or_value(name, value):
    with pytest.raises(ValueError):
        Fact(name, value)


def test_unknown_source():
    with pytest.raises(ValueError):
        Fact("sound", "squealing", source="guess")


def test_similarity_on_user_fact():
    with pytest.raises(ValueError):
        Fact("sound", "squealing", similarity=0.5)


@pytest.mark.parametrize("sim", [-0.1, 1.01])
def test_similarity_out_of_range(sim):
    with pytest.raises(ValueError):
        Fact("audio_match", "squealing", "audio", sim)
