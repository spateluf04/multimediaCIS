from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from carsense.knowledge.part import Part
from carsense.reasoning.rule import Rule

SELECT_TYPES = ("single", "multi")


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ValueError(f"{path.name}: file not found") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"{path.name}: invalid JSON ({e})") from e


def _duplicates(ids: list[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


class KnowledgeBase:
    """Rules, parts and questions loaded from the kb/ folder."""

    def __init__(
        self,
        rules: list[Rule],
        parts: list[Part],
        questions: list[dict[str, Any]],
    ) -> None:
        self._rules = rules
        self._parts = parts
        self._parts_by_id = {p.id: p for p in parts}
        self._questions = questions

    @classmethod
    def load(cls, path: str | Path) -> KnowledgeBase:
        folder = Path(path)
        rules_data = _read_json(folder / "rules.json")
        parts_data = _read_json(folder / "parts.json")
        questions = _read_json(folder / "questions.json")
        for name, data in (("rules.json", rules_data), ("parts.json", parts_data),
                           ("questions.json", questions)):
            if not isinstance(data, list):
                raise ValueError(f"{name}: expected a list")

        kb = cls(
            [Rule.from_dict(r) for r in rules_data],
            [Part.from_dict(p) for p in parts_data],
            questions,
        )
        kb.validate()
        return kb

    def rules(self) -> list[Rule]:
        return list(self._rules)

    def parts(self) -> list[Part]:
        return list(self._parts)

    def part(self, part_id: str) -> Part:
        try:
            return self._parts_by_id[part_id]
        except KeyError:
            raise KeyError(f"unknown part: {part_id}") from None

    def questions(self) -> list[dict[str, Any]]:
        return self._questions

    def options(self, fact: str) -> set[str]:
        for q in self._questions:
            if q.get("id") == fact:
                return {o.get("id") for o in q.get("options", [])}
        return set()

    def validate(self) -> None:
        """Raise ValueError if the files disagree with each other."""
        errors: list[str] = []

        q_ids = [q.get("id") for q in self._questions]
        for dup in _duplicates(q_ids):
            errors.append(f"duplicate question id: {dup}")
        for q in self._questions:
            if not q.get("id") or not q.get("text"):
                errors.append(f"question needs an id and text: {q!r}")
            if q.get("select") not in SELECT_TYPES:
                errors.append(f"question {q.get('id')}: select must be single or multi")
            opts = q.get("options") or []
            if not opts:
                errors.append(f"question {q.get('id')}: no options")
            if any(not o.get("id") or not o.get("label") for o in opts):
                errors.append(f"question {q.get('id')}: every option needs an id and label")
            for dup in _duplicates([o.get("id") for o in opts]):
                errors.append(f"question {q.get('id')}: duplicate option {dup}")

        for dup in _duplicates([r.id for r in self._rules]):
            errors.append(f"duplicate rule id: {dup}")
        for dup in _duplicates([p.id for p in self._parts]):
            errors.append(f"duplicate part id: {dup}")

        sounds = self.options("sound")
        for rule in self._rules:
            if rule.conclusion["part_id"] not in self._parts_by_id:
                errors.append(f"{rule.id}: unknown part_id {rule.conclusion['part_id']}")
            if rule.sound_type not in sounds:
                errors.append(f"{rule.id}: unknown sound_type {rule.sound_type}")
            for cond in rule.conditions:
                fact = cond["fact"]
                if fact not in q_ids:
                    errors.append(f"{rule.id}: no question for fact {fact}")
                    continue
                values = cond.get("any") or [cond.get("is") or cond.get("not")]
                unknown = [v for v in values if v not in self.options(fact)]
                if unknown:
                    errors.append(f"{rule.id}: {fact} has no option {unknown}")

        if errors:
            raise ValueError("knowledge base problems:\n  " + "\n  ".join(errors))
