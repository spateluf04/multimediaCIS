from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from carsense.reasoning.working_memory import WorkingMemory

CONDITION_TYPES = ("is", "any", "not")
URGENCY_LEVELS = ("Low", "Medium", "High", "Critical")
CONCLUSION_KEYS = ("problem", "part_id", "urgency", "safe", "cost")


def _check_condition(cond: Any, rule_id: str) -> None:
    if not isinstance(cond, dict) or not cond.get("fact"):
        raise ValueError(f"{rule_id}: condition needs a fact: {cond!r}")
    kinds = [k for k in cond if k != "fact"]
    if len(kinds) != 1 or kinds[0] not in CONDITION_TYPES:
        raise ValueError(f"{rule_id}: condition needs exactly one of {CONDITION_TYPES}: {cond!r}")
    kind = kinds[0]
    if kind == "any":
        if not isinstance(cond["any"], list) or not cond["any"]:
            raise ValueError(f"{rule_id}: 'any' needs a non-empty list: {cond!r}")
    elif not isinstance(cond[kind], str) or not cond[kind]:
        raise ValueError(f"{rule_id}: '{kind}' needs a value: {cond!r}")


def condition_holds(cond: dict[str, Any], wm: WorkingMemory) -> bool:
    name = cond["fact"]
    if "is" in cond:
        return wm.has(name, cond["is"])
    if "any" in cond:
        return not wm.values(name).isdisjoint(cond["any"])
    return not wm.has(name, cond["not"])


@dataclass
class Rule:
    """One diagnostic rule loaded from rules.json."""

    id: str
    sound_type: str
    certainty: float
    conditions: list[dict[str, Any]] = field(default_factory=list)
    conclusion: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        rule_id = data.get("id") or "<no id>"
        for key in ("id", "sound_type", "certainty", "conditions", "conclusion"):
            if key not in data:
                raise ValueError(f"{rule_id}: missing '{key}'")

        certainty = data["certainty"]
        if not isinstance(certainty, (int, float)) or not 0.0 <= certainty <= 1.0:
            raise ValueError(f"{rule_id}: certainty must be between 0 and 1")

        conditions = data["conditions"]
        if not isinstance(conditions, list) or not conditions:
            raise ValueError(f"{rule_id}: needs at least one condition")
        for cond in conditions:
            _check_condition(cond, rule_id)

        conclusion = data["conclusion"]
        missing = [k for k in CONCLUSION_KEYS if not conclusion.get(k)]
        if missing:
            raise ValueError(f"{rule_id}: conclusion missing {missing}")
        if conclusion["urgency"] not in URGENCY_LEVELS:
            raise ValueError(f"{rule_id}: unknown urgency {conclusion['urgency']!r}")

        return cls(
            id=data["id"],
            sound_type=data["sound_type"],
            certainty=float(certainty),
            conditions=copy.deepcopy(conditions),
            conclusion=dict(conclusion),
        )

    def matches(self, wm: WorkingMemory) -> bool:
        return all(condition_holds(c, wm) for c in self.conditions)

    def match_ratio(self, wm: WorkingMemory) -> float:
        return len(self.matched_conditions(wm)) / len(self.conditions)

    def matched_conditions(self, wm: WorkingMemory) -> list[dict[str, Any]]:
        return [c for c in self.conditions if condition_holds(c, wm)]

    def missing_conditions(self, wm: WorkingMemory) -> list[dict[str, Any]]:
        return [c for c in self.conditions if not condition_holds(c, wm)]
