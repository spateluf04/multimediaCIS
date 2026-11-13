import json
import shutil

import pytest
from conftest import KB_DIR

from carsense.knowledge.knowledge_base import KnowledgeBase
from carsense.reasoning.working_memory import WorkingMemory


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load(KB_DIR)


@pytest.fixture
def kb_copy(tmp_path):
    for name in ("rules.json", "parts.json", "questions.json"):
        shutil.copy(KB_DIR / name, tmp_path / name)
    return tmp_path


def edit(folder, name, change):
    path = folder / name
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_loads_real_kb(kb):
    assert len(kb.rules()) == 12
    assert len(kb.parts()) == 12
    assert [q["id"] for q in kb.questions()] == ["sound", "timing", "location", "symptom"]


def test_rule_ids_in_order(kb):
    assert [r.id for r in kb.rules()] == [f"R{i}" for i in range(1, 13)]


def test_every_rule_has_its_part(kb):
    for rule in kb.rules():
        assert kb.part(rule.conclusion["part_id"]).cost_level == rule.conclusion["cost"]


def test_options(kb):
    assert len(kb.options("sound")) == 9
    assert len(kb.options("timing")) == 9
    assert kb.options("location") == {"wheels", "engine_bay", "engine_top", "engine_lower", "underneath"}
    assert len(kb.options("symptom")) == 6
    assert kb.options("audio_match") == set()


def test_unknown_part(kb):
    with pytest.raises(KeyError):
        kb.part("muffler")


def test_rules_returns_copy(kb):
    kb.rules().clear()
    assert len(kb.rules()) == 12


def answers_for(rule):
    """Smallest set of answers that satisfies every condition of a rule."""
    answers = {}
    for cond in rule.conditions:
        if "not" in cond:
            continue
        value = cond.get("is") or cond["any"][0]
        answers.setdefault(cond["fact"], []).append(value)
    return answers


@pytest.mark.parametrize("index", range(12))
def test_each_rule_can_fire(kb, index):
    rule = kb.rules()[index]
    assert rule.matches(WorkingMemory.from_answers(answers_for(rule)))


def test_r7_and_r8_split_by_smell(kb):
    rules = {r.id: r for r in kb.rules()}
    base = {"sound": "hissing", "location": "engine_bay"}
    smell = WorkingMemory.from_answers({**base, "symptom": ["sweet_smell", "rough_idle"]})
    no_smell = WorkingMemory.from_answers({**base, "symptom": ["rough_idle"]})
    assert rules["R7"].matches(smell) and not rules["R8"].matches(smell)
    assert rules["R8"].matches(no_smell) and not rules["R7"].matches(no_smell)


def expect_error(folder, text):
    with pytest.raises(ValueError, match=text):
        KnowledgeBase.load(folder)


def test_duplicate_rule_id(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[1].update(id="R1"))
    expect_error(kb_copy, "duplicate rule id: R1")


def test_unknown_part_id(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[0]["conclusion"].update(part_id="muffler"))
    expect_error(kb_copy, "R1: unknown part_id muffler")


def test_unknown_condition_type(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[0]["conditions"].append({"fact": "sound", "maybe": "x"}))
    expect_error(kb_copy, "exactly one of")


def test_condition_value_not_in_questions(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[2]["conditions"][1]["any"].append("reversing"))
    expect_error(kb_copy, r"R3: timing has no option \['reversing'\]")


def test_not_value_checked(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[7]["conditions"][3].update({"not": "burnt_smell"}))
    expect_error(kb_copy, "R8: symptom has no option")


def test_condition_fact_not_a_question(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[0]["conditions"].append({"fact": "weather", "is": "rain"}))
    expect_error(kb_copy, "R1: no question for fact weather")


def test_unknown_sound_type(kb_copy):
    edit(kb_copy, "rules.json", lambda d: d[0].update(sound_type="screech"))
    expect_error(kb_copy, "R1: unknown sound_type screech")


def test_option_removed_from_questions(kb_copy):
    def drop_braking(questions):
        timing = questions[1]
        timing["options"] = [o for o in timing["options"] if o["id"] != "braking"]
    edit(kb_copy, "questions.json", drop_braking)
    expect_error(kb_copy, r"R1: timing has no option \['braking'\]")


def test_duplicate_part_id(kb_copy):
    edit(kb_copy, "parts.json", lambda d: d.append(dict(d[0])))
    expect_error(kb_copy, "duplicate part id: brake_pads")


def test_duplicate_option(kb_copy):
    edit(kb_copy, "questions.json", lambda d: d[0]["options"].append(dict(d[0]["options"][0])))
    expect_error(kb_copy, "sound: duplicate option squealing")


def test_duplicate_question(kb_copy):
    edit(kb_copy, "questions.json", lambda d: d.append(dict(d[0])))
    expect_error(kb_copy, "duplicate question id: sound")


def test_bad_select(kb_copy):
    edit(kb_copy, "questions.json", lambda d: d[0].update(select="dropdown"))
    expect_error(kb_copy, "sound: select must be single or multi")


def test_option_without_label(kb_copy):
    edit(kb_copy, "questions.json", lambda d: d[0]["options"][0].pop("label"))
    expect_error(kb_copy, "every option needs an id and label")


def test_reports_every_problem(kb_copy):
    edit(kb_copy, "rules.json", lambda d: (d[0].update(sound_type="x"), d[1]["conclusion"].update(part_id="y")))
    with pytest.raises(ValueError) as err:
        KnowledgeBase.load(kb_copy)
    assert "R1: unknown sound_type" in str(err.value)
    assert "R2: unknown part_id" in str(err.value)


def test_missing_file(kb_copy):
    (kb_copy / "parts.json").unlink()
    expect_error(kb_copy, "parts.json: file not found")


def test_invalid_json(kb_copy):
    (kb_copy / "rules.json").write_text("[{", encoding="utf-8")
    expect_error(kb_copy, "rules.json: invalid JSON")


def test_not_a_list(kb_copy):
    (kb_copy / "parts.json").write_text("{}", encoding="utf-8")
    expect_error(kb_copy, "parts.json: expected a list")
