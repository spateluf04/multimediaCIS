from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from carsense.reasoning.rule import URGENCY_LEVELS, Rule

KINDS = ("fired", "partial")


@dataclass
class Diagnosis:
    """One ranked result returned by the inference engine."""

    rule_id: str
    problem: str
    part_id: str
    urgency: str
    safe: str
    cost: str
    confidence: float
    kind: str
    matched: list[dict[str, Any]] = field(default_factory=list)
    missing: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind: {self.kind!r}")
        if self.urgency not in URGENCY_LEVELS:
            raise ValueError(f"unknown urgency: {self.urgency!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")

    @classmethod
    def from_rule(
        cls,
        rule: Rule,
        confidence: float,
        kind: str,
        matched: list[dict[str, Any]] | None = None,
        missing: list[dict[str, Any]] | None = None,
    ) -> Diagnosis:
        c = rule.conclusion
        return cls(
            rule_id=rule.id,
            problem=c["problem"],
            part_id=c["part_id"],
            urgency=c["urgency"],
            safe=c["safe"],
            cost=c["cost"],
            confidence=confidence,
            kind=kind,
            matched=list(matched or []),
            missing=list(missing or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "problem": self.problem,
            "part_id": self.part_id,
            "urgency": self.urgency,
            "safe": self.safe,
            "cost": self.cost,
            "confidence": round(self.confidence, 3),
            "kind": self.kind,
            "matched": list(self.matched),
            "missing": list(self.missing),
            "notes": list(self.notes),
        }
