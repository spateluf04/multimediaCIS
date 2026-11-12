from __future__ import annotations

from dataclasses import dataclass

SOURCES = ("user", "audio")


@dataclass(frozen=True)
class Fact:
    """A single piece of evidence, like sound=squealing."""

    name: str
    value: str
    source: str = "user"
    similarity: float | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.value:
            raise ValueError("fact needs a name and a value")
        if self.source not in SOURCES:
            raise ValueError(f"unknown source: {self.source!r}")
        if self.similarity is not None:
            if self.source != "audio":
                raise ValueError("only audio facts have a similarity")
            if not 0.0 <= self.similarity <= 1.0:
                raise ValueError(f"similarity out of range: {self.similarity}")
