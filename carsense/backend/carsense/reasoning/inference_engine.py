from __future__ import annotations

from typing import Any

from carsense.knowledge.knowledge_base import KnowledgeBase
from carsense.reasoning.diagnosis import Diagnosis
from carsense.reasoning.rule import URGENCY_LEVELS
from carsense.reasoning.working_memory import WorkingMemory

STOP_DRIVING = "STOP_DRIVING"
SEE_MECHANIC = "SEE_MECHANIC"


class InferenceEngine:
    """Single-pass forward matching of rules against working memory.

    Every rule is checked against the facts once, the meta-rules adjust and
    rank the results, and conclusions never feed back into other rules.
    """

    BASE_CERTAINTY = 0.70
    AUDIO_BOOST = 0.25
    CONFIDENCE_CAP = 0.95
    PARTIAL_FACTOR = 0.6
    ALT_THRESHOLD = 0.30
    UNCERTAIN_THRESHOLD = 0.50

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self._sound_types = {r.id: r.sound_type for r in kb.rules()}
        self._order = {r.id: i for i, r in enumerate(kb.rules())}

    def run(self, wm: WorkingMemory) -> dict[str, Any]:
        diagnoses = self._evaluate(wm)
        self._apply_m2(diagnoses, wm)
        diagnoses = self._rank(diagnoses)
        warnings: list[str] = []
        self._apply_m1(diagnoses, warnings)
        uncertain = self._apply_m3(diagnoses, warnings)
        return {"diagnoses": diagnoses, "warnings": warnings, "uncertain": uncertain}

    def _evaluate(self, wm: WorkingMemory) -> list[Diagnosis]:
        results = []
        for rule in self.kb.rules():
            matched = rule.matched_conditions(wm)
            missing = rule.missing_conditions(wm)
            if not missing:
                results.append(Diagnosis.from_rule(rule, rule.certainty, "fired", matched, missing))
                continue
            confidence = rule.match_ratio(wm) * rule.certainty * self.PARTIAL_FACTOR
            if confidence >= self.ALT_THRESHOLD:
                results.append(Diagnosis.from_rule(rule, confidence, "partial", matched, missing))
        return results

    def _apply_m2(self, diagnoses: list[Diagnosis], wm: WorkingMemory) -> None:
        audio = wm.audio_match()
        if audio is None:
            return
        similarity = audio.similarity or 0.0
        user_sounds = wm.values("sound")
        disagrees = bool(user_sounds) and audio.value not in user_sounds

        for d in diagnoses:
            if self._sound_types[d.rule_id] == audio.value:
                boosted = min(d.confidence + self.AUDIO_BOOST * similarity, self.CONFIDENCE_CAP)
                added = max(boosted - d.confidence, 0.0)
                d.confidence = max(d.confidence, boosted)
                d.notes.append(
                    f"M2: audio match ({audio.value}, {similarity:.2f}) agrees, "
                    f"confidence +{added:.2f}"
                )
            elif disagrees:
                d.notes.append(
                    f"M2: audio match ({audio.value}, {similarity:.2f}) disagrees with "
                    f"the chosen sound, confidence unchanged"
                )

    def _rank(self, diagnoses: list[Diagnosis]) -> list[Diagnosis]:
        return sorted(
            diagnoses,
            key=lambda d: (
                -round(d.confidence, 6),
                -URGENCY_LEVELS.index(d.urgency),
                self._order[d.rule_id],
            ),
        )

    def _apply_m1(self, diagnoses: list[Diagnosis], warnings: list[str]) -> None:
        if any(d.urgency == "Critical" for d in diagnoses):
            warnings.insert(0, STOP_DRIVING)

    def _apply_m3(self, diagnoses: list[Diagnosis], warnings: list[str]) -> bool:
        fired = any(d.kind == "fired" for d in diagnoses)
        top = diagnoses[0].confidence if diagnoses else 0.0
        if not fired or top < self.UNCERTAIN_THRESHOLD:
            warnings.append(SEE_MECHANIC)
            return True
        return False
