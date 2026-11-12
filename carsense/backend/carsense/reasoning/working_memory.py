from __future__ import annotations

from typing import Any

from carsense.reasoning.fact import Fact

AUDIO_FACT = "audio_match"


class WorkingMemory:
    """The facts known about the current session."""

    def __init__(self) -> None:
        self._facts: dict[str, set[Fact]] = {}

    def assert_fact(self, fact: Fact) -> None:
        self._facts.setdefault(fact.name, set()).add(fact)

    def has(self, name: str, value: str) -> bool:
        return value in self.values(name)

    def values(self, name: str) -> set[str]:
        return {f.value for f in self._facts.get(name, ())}

    def audio_match(self) -> Fact | None:
        matches = self._facts.get(AUDIO_FACT)
        if not matches:
            return None
        return max(matches, key=lambda f: f.similarity or 0.0)

    def facts(self) -> list[Fact]:
        return sorted(
            (f for group in self._facts.values() for f in group),
            key=lambda f: (f.name, f.value, f.source),
        )

    def clear(self) -> None:
        self._facts.clear()

    def __len__(self) -> int:
        return sum(len(group) for group in self._facts.values())

    @classmethod
    def from_answers(
        cls, answers: dict[str, Any], audio: dict[str, Any] | None = None
    ) -> WorkingMemory:
        """Build memory from the request answers and an optional audio match."""
        wm = cls()
        for name, answer in answers.items():
            items = [answer] if isinstance(answer, str) else (answer or [])
            for value in items:
                if value:
                    wm.assert_fact(Fact(name, value))

        if audio is not None:
            try:
                sound = audio["sound"]
                similarity = float(audio["similarity"])
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"bad audio match: {audio!r}") from e
            wm.assert_fact(Fact(AUDIO_FACT, sound, "audio", similarity))
        return wm
