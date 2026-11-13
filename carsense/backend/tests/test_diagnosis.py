import pytest

from carsense.reasoning.diagnosis import Diagnosis
from carsense.reasoning.rule import Rule
from carsense.reasoning.working_memory import WorkingMemory

R1 = Rule.from_dict({
    "id": "R1",
    "sound_type": "squealing",
    "certainty": 0.70,
    "conditions": [
        {"fact": "sound", "is": "squealing"},
        {"fact": "timing", "is": "braking"},
        {"fact": "location", "is": "wheels"},
    ],
    "conclusion": {
        "problem": "Worn brake pads",
        "part_id": "brake_pads",
        "urgency": "Medium",
        "safe": "Yes, but repair soon",
        "cost": "Low",
    },
})


def make(**overrides):
    args = {"confidence": 0.7, "kind": "fired"}
    args.update(overrides)
    return Diagnosis.from_rule(R1, **args)


def test_from_rule():
    wm = WorkingMemory.from_answers({"sound": "squealing", "timing": ["braking"]})
    d = Diagnosis.from_rule(
        R1, 0.28, "partial", R1.matched_conditions(wm), R1.missing_conditions(wm)
    )
    assert d.rule_id == "R1"
    assert d.problem == "Worn brake pads"
    assert d.part_id == "brake_pads"
    assert d.urgency == "Medium"
    assert d.safe == "Yes, but repair soon"
    assert d.cost == "Low"
    assert d.kind == "partial"
    assert len(d.matched) == 2
    assert d.missing == [{"fact": "location", "is": "wheels"}]
    assert d.notes == []


def test_to_dict_shape():
    d = make(matched=list(R1.conditions))
    d.notes.append("M2: audio agrees")
    assert d.to_dict() == {
        "rule_id": "R1",
        "problem": "Worn brake pads",
        "part_id": "brake_pads",
        "urgency": "Medium",
        "safe": "Yes, but repair soon",
        "cost": "Low",
        "confidence": 0.7,
        "kind": "fired",
        "matched": R1.conditions,
        "missing": [],
        "notes": ["M2: audio agrees"],
    }


def test_to_dict_rounds_confidence():
    assert make(confidence=0.31500000001).to_dict()["confidence"] == 0.315


def test_confidence_can_change():
    d = make()
    d.confidence = 0.9
    assert d.to_dict()["confidence"] == 0.9


def test_lists_not_shared():
    matched = [{"fact": "sound", "is": "squealing"}]
    a = make(matched=matched)
    b = make()
    a.notes.append("x")
    matched.append({"fact": "timing", "is": "braking"})
    assert b.notes == []
    assert len(a.matched) == 1
    a.to_dict()["notes"].append("y")
    assert a.notes == ["x"]


def test_bad_kind():
    with pytest.raises(ValueError):
        make(kind="maybe")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_bad_confidence(confidence):
    with pytest.raises(ValueError):
        make(confidence=confidence)


def test_bad_urgency():
    with pytest.raises(ValueError):
        Diagnosis("R1", "p", "brake_pads", "Urgent", "Yes", "Low", 0.5, "fired")
