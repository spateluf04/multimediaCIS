import copy

import pytest

from carsense.reasoning.rule import Rule
from carsense.reasoning.working_memory import WorkingMemory

ENGINE_BAY = ["engine_bay", "engine_top", "engine_lower"]

R3 = {
    "id": "R3",
    "sound_type": "squealing",
    "certainty": 0.70,
    "conditions": [
        {"fact": "sound", "is": "squealing"},
        {"fact": "timing", "any": ["starting", "accelerating"]},
        {"fact": "location", "any": ENGINE_BAY},
    ],
    "conclusion": {
        "problem": "Loose or worn drive belt",
        "part_id": "drive_belt",
        "urgency": "Medium",
        "safe": "Yes, for short trips",
        "cost": "Low",
    },
}

R8 = {
    "id": "R8",
    "sound_type": "hissing",
    "certainty": 0.70,
    "conditions": [
        {"fact": "sound", "is": "hissing"},
        {"fact": "location", "any": ENGINE_BAY},
        {"fact": "symptom", "is": "rough_idle"},
        {"fact": "symptom", "not": "sweet_smell"},
    ],
    "conclusion": {
        "problem": "Vacuum leak",
        "part_id": "vacuum_hose",
        "urgency": "Medium",
        "safe": "Yes",
        "cost": "Low",
    },
}


def wm(**answers):
    return WorkingMemory.from_answers(answers)


def test_from_dict():
    rule = Rule.from_dict(R3)
    assert rule.id == "R3"
    assert rule.sound_type == "squealing"
    assert rule.certainty == 0.70
    assert len(rule.conditions) == 3
    assert rule.conclusion["part_id"] == "drive_belt"


def test_from_dict_copies_input():
    data = copy.deepcopy(R3)
    rule = Rule.from_dict(data)
    data["conditions"].pop()
    data["conditions"][1]["any"].append("idling")
    data["conclusion"]["cost"] = "High"
    assert len(rule.conditions) == 3
    assert rule.conditions[1]["any"] == ["starting", "accelerating"]
    assert rule.conclusion["cost"] == "Low"


def test_is_condition():
    rule = Rule.from_dict(R3)
    assert rule.matches(wm(sound="squealing", timing=["starting"], location="engine_top"))
    assert not rule.matches(wm(sound="grinding", timing=["starting"], location="engine_top"))


def test_any_condition_one_of_several():
    rule = Rule.from_dict(R3)
    facts = wm(sound="squealing", timing=["idling", "accelerating"], location="engine_bay")
    assert rule.matches(facts)


def test_any_condition_none_present():
    rule = Rule.from_dict(R3)
    assert not rule.matches(wm(sound="squealing", timing=["braking"], location="engine_bay"))


def test_not_condition():
    rule = Rule.from_dict(R8)
    assert rule.matches(wm(sound="hissing", location="engine_bay", symptom=["rough_idle"]))
    assert not rule.matches(
        wm(sound="hissing", location="engine_bay", symptom=["rough_idle", "sweet_smell"])
    )


def test_not_condition_holds_on_empty_memory():
    rule = Rule.from_dict(R8)
    assert rule.matched_conditions(WorkingMemory()) == [{"fact": "symptom", "not": "sweet_smell"}]


@pytest.mark.parametrize("answers, ratio", [
    ({"sound": "squealing", "timing": ["starting"], "location": "engine_bay"}, 1.0),
    ({"sound": "squealing", "timing": ["starting"]}, 2 / 3),
    ({"sound": "squealing"}, 1 / 3),
    ({}, 0.0),
])
def test_match_ratio(answers, ratio):
    assert Rule.from_dict(R3).match_ratio(wm(**answers)) == pytest.approx(ratio)


def test_matched_and_missing():
    rule = Rule.from_dict(R8)
    facts = wm(sound="hissing", location="engine_lower")
    assert rule.matched_conditions(facts) == [R8["conditions"][0], R8["conditions"][1], R8["conditions"][3]]
    assert rule.missing_conditions(facts) == [R8["conditions"][2]]
    assert rule.match_ratio(facts) == 0.75


def test_matched_and_missing_cover_all_conditions():
    rule = Rule.from_dict(R3)
    facts = wm(sound="squealing", location="wheels")
    assert len(rule.matched_conditions(facts)) + len(rule.missing_conditions(facts)) == 3


def broken(path, value=None, delete=False):
    data = copy.deepcopy(R3)
    target = data
    for key in path[:-1]:
        target = target[key]
    if delete:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return data


@pytest.mark.parametrize("key", ["id", "sound_type", "certainty", "conditions", "conclusion"])
def test_missing_top_level_key(key):
    with pytest.raises(ValueError):
        Rule.from_dict(broken([key], delete=True))


@pytest.mark.parametrize("certainty", [-0.1, 1.2, "high"])
def test_bad_certainty(certainty):
    with pytest.raises(ValueError):
        Rule.from_dict(broken(["certainty"], certainty))


@pytest.mark.parametrize("cond", [
    {"fact": "sound", "equals": "squealing"},
    {"fact": "sound", "is": "squealing", "not": "grinding"},
    {"fact": "sound"},
    {"is": "squealing"},
    {"fact": "timing", "any": []},
    {"fact": "timing", "any": "starting"},
    {"fact": "sound", "is": ""},
    "sound=squealing",
])
def test_bad_condition(cond):
    with pytest.raises(ValueError):
        Rule.from_dict(broken(["conditions", 0], cond))


def test_no_conditions():
    with pytest.raises(ValueError):
        Rule.from_dict(broken(["conditions"], []))


@pytest.mark.parametrize("key", ["problem", "part_id", "urgency", "safe", "cost"])
def test_conclusion_missing_key(key):
    with pytest.raises(ValueError):
        Rule.from_dict(broken(["conclusion", key], delete=True))


def test_unknown_urgency():
    with pytest.raises(ValueError):
        Rule.from_dict(broken(["conclusion", "urgency"], "Urgent"))
