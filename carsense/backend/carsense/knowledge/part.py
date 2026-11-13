from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Part:
    """A car part a diagnosis can point to, with its media."""

    id: str
    name: str
    cost_level: str
    description: str = ""
    images: list[str] = field(default_factory=list)
    video: str | None = None
    cost_range: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Part:
        missing = [k for k in ("id", "name", "cost_level") if not data.get(k)]
        if missing:
            raise ValueError(f"part {data.get('id', '<no id>')}: missing {missing}")
        return cls(
            id=data["id"],
            name=data["name"],
            cost_level=data["cost_level"],
            description=data.get("description") or "",
            images=list(data.get("images") or []),
            video=data.get("video"),
            cost_range=data.get("cost_range"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cost_level": self.cost_level,
            "description": self.description,
            "images": list(self.images),
            "video": self.video,
            "cost_range": self.cost_range,
        }
