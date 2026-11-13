import copy

import pytest
from conftest import KB_DIR

from carsense.knowledge.knowledge_base import KnowledgeBase
from carsense.reasoning.inference_engine import SEE_MECHANIC, STOP_DRIVING, InferenceEngine
from carsense.reasoning.working_memory import WorkingMemory


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load(KB_DIR)


@pytest.fixture(scope="module")
def engine(kb):
    return InferenceEngine(kb)


def run(engine, audio=None, **answers):
    return engine.run(WorkingMemory.from_answers(answers, audio))


def ids(result):
    return [d.rule_id for d in result["diagnoses"]]


CASES = [
    ("R1", {"sound": "squealing", "timing": ["braking"], "location": "wheels"},
     "Worn brake pads", "Medium", "Yes, but repair soon", "Low"),
    ("R2", {"sound": "grinding", "timing": ["braking"], "location": "wheels"},
     "Brake pads worn to metal, damaging the rotors", "High", "No", "Medium"),
    ("R3", {"sound": "squealing", "timing": ["accelerating"], "location": "engine_bay"},
     "Loose or worn drive belt", "Medium", "Yes, for short trips", "Low"),
    ("R4", {"sound": "clicking", "timing": ["turning"], "location": "wheels"},
     "Worn CV joint", "Medium", "Yes, but repair soon", "Medium"),
    ("R5", {"sound": "knocking", "timing": ["with_engine_speed"], "location": "engine_lower"},
     "Rod knock (serious internal engine wear)", "Critical", "No", "High"),
    ("R6", {"sound": "ticking", "timing": ["idling"], "location": "engine_top"},
     "Lifter tick, often from low or old oil", "Low", "Yes, check the oil first", "Low to Medium"),
    ("R7", {"sound": "hissing", "location": "engine_bay", "symptom": ["running_hot"]},
     "Coolant leak", "High", "No", "Medium"),
    ("R8", {"sound": "hissing", "location": "engine_top", "symptom": ["rough_idle"]},
     "Vacuum leak", "Medium", "Yes", "Low"),
    ("R9", {"sound": "clicking", "timing": ["starting"], "symptom": ["wont_start"]},
     "Weak battery or loose battery connection", "Medium", "Car will not start", "Low"),
    ("R10", {"sound": "humming", "timing": ["with_vehicle_speed"], "location": "wheels"},
     "Failing wheel bearing", "High", "Short distances only", "Medium"),
    ("R11", {"sound": "clunking", "timing": ["over_bumps"], "location": "underneath"},
     "Worn suspension parts", "Medium", "Yes, but inspect soon", "Medium"),
    ("R12", {"sound": "whining", "timing": ["steering"], "location": "engine_lower"},
     "Low power steering fluid or failing pump", "Low", "Yes", "Low to Medium"),
]


@pytest.mark.parametrize("rule_id, answers, problem, urgency, safe, cost", CASES,
                         ids=[c[0] for c in CASES])
def test_each_rule(engine, rule_id, answers, problem, urgency, safe, cost):
    result = engine.run(WorkingMemory.from_answers(answers))
    top = result["diagnoses"][0]
    assert top.rule_id == rule_id
    assert top.kind == "fired"
    assert top.confidence == pytest.approx(0.70)
    assert (top.problem, top.urgency, top.safe, top.cost) == (problem, urgency, safe, cost)
    assert not result["uncertain"]
    assert [d.rule_id for d in result["diagnoses"] if d.kind == "fired"] == [rule_id]


def test_kb_rules_use_base_certainty(kb):
    assert all(r.certainty == InferenceEngine.BASE_CERTAINTY for r in kb.rules())


def test_m1_stop_driving_first(engine):
    result = run(engine, sound="knocking", timing=["with_engine_speed"], location="engine_lower")
    assert result["warnings"][0] == STOP_DRIVING
    assert result["diagnoses"][0].urgency == "Critical"


def test_m1_not_raised_without_critical(engine):
    result = run(engine, sound="grinding", timing=["braking"], location="wheels")
    assert STOP_DRIVING not in result["warnings"]


def test_m1_comes_before_m3(kb):
    r5 = copy.deepcopy(kb.rules()[4])
    r5.conditions.append({"fact": "symptom", "is": "warning_light"})
    engine = InferenceEngine(KnowledgeBase([r5], kb.parts(), kb.questions()))
    result = run(engine, sound="knocking", timing=["with_engine_speed"], location="engine_lower")
    assert result["diagnoses"][0].kind == "partial"
    assert result["warnings"] == [STOP_DRIVING, SEE_MECHANIC]


def test_m2_boost(engine):
    result = run(engine, {"sound": "squealing", "similarity": 0.8},
                 sound="squealing", timing=["braking"], location="wheels")
    top = result["diagnoses"][0]
    assert top.confidence == pytest.approx(0.90)
    assert top.notes == ["M2: audio match (squealing, 0.80) agrees, confidence +0.20"]


def test_m2_full_similarity_reaches_cap(engine):
    result = run(engine, {"sound": "humming", "similarity": 1.0},
                 sound="humming", timing=["with_vehicle_speed"], location="wheels")
    assert result["diagnoses"][0].confidence == pytest.approx(InferenceEngine.CONFIDENCE_CAP)


def test_m2_cap(kb):
    rule = copy.deepcopy(kb.rules()[0])
    rule.certainty = 0.9
    engine = InferenceEngine(KnowledgeBase([rule], kb.parts(), kb.questions()))
    result = run(engine, {"sound": "squealing", "similarity": 0.9},
                 sound="squealing", timing=["braking"], location="wheels")
    top = result["diagnoses"][0]
    assert top.confidence == pytest.approx(0.95)
    assert top.notes == ["M2: audio match (squealing, 0.90) agrees, confidence +0.05"]


def test_m2_boosts_partial(engine):
    result = run(engine, {"sound": "hissing", "similarity": 0.6}, sound="hissing", location="engine_bay")
    r8 = result["diagnoses"][0]
    assert r8.rule_id == "R8"
    assert r8.confidence == pytest.approx(0.315 + 0.15)
    assert result["uncertain"]


def test_m2_disagreement(engine):
    result = run(engine, {"sound": "grinding", "similarity": 0.7},
                 sound="squealing", timing=["braking"], location="wheels")
    top = result["diagnoses"][0]
    assert top.rule_id == "R1"
    assert top.confidence == pytest.approx(0.70)
    assert top.notes == [
        "M2: audio match (grinding, 0.70) disagrees with the chosen sound, confidence unchanged"
    ]


def test_m2_zero_similarity(engine):
    result = run(engine, {"sound": "squealing", "similarity": 0.0},
                 sound="squealing", timing=["braking"], location="wheels")
    assert result["diagnoses"][0].confidence == pytest.approx(0.70)


def test_audio_alone_is_not_a_diagnosis(engine):
    result = run(engine, {"sound": "grinding", "similarity": 0.95})
    assert result["diagnoses"] == []
    assert result["uncertain"]


def test_m3_no_match(engine):
    result = run(engine, sound="whining", timing=["braking"], location="underneath")
    assert result["diagnoses"] == []
    assert result["warnings"] == [SEE_MECHANIC]
    assert result["uncertain"]


def test_m3_low_confidence_partial(engine):
    result = run(engine, sound="hissing", location="engine_bay")
    assert ids(result) == ["R8"]
    assert result["diagnoses"][0].kind == "partial"
    assert result["diagnoses"][0].confidence == pytest.approx(0.315)
    assert result["uncertain"]
    assert result["warnings"] == [SEE_MECHANIC]


def test_m3_low_top_confidence_even_if_fired(kb):
    rule = copy.deepcopy(kb.rules()[0])
    rule.certainty = 0.4
    engine = InferenceEngine(KnowledgeBase([rule], kb.parts(), kb.questions()))
    result = run(engine, sound="squealing", timing=["braking"], location="wheels")
    assert result["diagnoses"][0].kind == "fired"
    assert result["uncertain"]


def test_partial_listed_as_alternative(engine):
    result = run(engine, sound="hissing", location="engine_bay", symptom=["running_hot"])
    assert ids(result) == ["R7", "R8"]
    r8 = result["diagnoses"][1]
    assert r8.kind == "partial"
    assert r8.missing == [{"fact": "symptom", "is": "rough_idle"}]
    assert not result["uncertain"]


def test_two_of_three_is_below_threshold(engine):
    result = run(engine, sound="squealing", timing=["braking"])
    assert result["diagnoses"] == []


def test_r7_vs_r8_by_symptoms(engine):
    smell = run(engine, sound="hissing", location="engine_bay", symptom=["sweet_smell", "rough_idle"])
    no_smell = run(engine, sound="hissing", location="engine_bay", symptom=["rough_idle"])
    assert [d.rule_id for d in smell["diagnoses"] if d.kind == "fired"] == ["R7"]
    assert [d.rule_id for d in no_smell["diagnoses"] if d.kind == "fired"] == ["R8"]


def test_both_hissing_rules_can_fire(engine):
    result = run(engine, sound="hissing", location="engine_bay", symptom=["running_hot", "rough_idle"])
    assert ids(result) == ["R7", "R8"]


def test_tie_broken_by_urgency(engine):
    result = run(engine, sound="hissing", location="engine_bay", symptom=["running_hot", "rough_idle"])
    r7, r8 = result["diagnoses"]
    assert r7.confidence == r8.confidence
    assert (r7.urgency, r8.urgency) == ("High", "Medium")


def test_tie_with_same_urgency_uses_rule_order(kb):
    first, second = copy.deepcopy(kb.rules()[0]), copy.deepcopy(kb.rules()[0])
    first.id, second.id = "B", "A"
    engine = InferenceEngine(KnowledgeBase([first, second], kb.parts(), kb.questions()))
    result = run(engine, sound="squealing", timing=["braking"], location="wheels")
    assert ids(result) == ["B", "A"]


def test_empty_memory(engine):
    result = engine.run(WorkingMemory())
    assert result == {"diagnoses": [], "warnings": [SEE_MECHANIC], "uncertain": True}


def test_unknown_values(engine):
    result = run(engine, sound="banging", timing=["reversing"], location="trunk")
    assert result["diagnoses"] == []
    assert result["uncertain"]


def test_same_input_same_output(engine):
    answers = {"sound": "hissing", "location": "engine_bay", "symptom": ["running_hot"]}
    a = engine.run(WorkingMemory.from_answers(answers))
    b = engine.run(WorkingMemory.from_answers(answers))
    assert [d.to_dict() for d in a["diagnoses"]] == [d.to_dict() for d in b["diagnoses"]]


def test_does_not_change_memory(engine):
    wm = WorkingMemory.from_answers({"sound": "squealing", "timing": ["braking"]})
    before = wm.facts()
    engine.run(wm)
    assert wm.facts() == before


def as_json(result):
    return {**result, "diagnoses": [d.to_dict() for d in result["diagnoses"]]}


def test_core_api_example_1(engine):
    result = run(engine, {"sound": "squealing", "similarity": 0.8},
                 sound="squealing", timing=["braking"], location="wheels", symptom=[])
    assert as_json(result) == {
        "diagnoses": [{
            "rule_id": "R1",
            "problem": "Worn brake pads",
            "part_id": "brake_pads",
            "urgency": "Medium",
            "safe": "Yes, but repair soon",
            "cost": "Low",
            "confidence": 0.9,
            "kind": "fired",
            "matched": [
                {"fact": "sound", "is": "squealing"},
                {"fact": "timing", "is": "braking"},
                {"fact": "location", "is": "wheels"},
            ],
            "missing": [],
            "notes": ["M2: audio match (squealing, 0.80) agrees, confidence +0.20"],
        }],
        "warnings": [],
        "uncertain": False,
    }


def test_core_api_example_2(engine):
    result = run(engine, sound="hissing", location="engine_bay")
    assert as_json(result) == {
        "diagnoses": [{
            "rule_id": "R8",
            "problem": "Vacuum leak",
            "part_id": "vacuum_hose",
            "urgency": "Medium",
            "safe": "Yes",
            "cost": "Low",
            "confidence": 0.315,
            "kind": "partial",
            "matched": [
                {"fact": "sound", "is": "hissing"},
                {"fact": "location", "any": ["engine_bay", "engine_top", "engine_lower"]},
                {"fact": "symptom", "not": "sweet_smell"},
            ],
            "missing": [{"fact": "symptom", "is": "rough_idle"}],
            "notes": [],
        }],
        "warnings": [SEE_MECHANIC],
        "uncertain": True,
    }
