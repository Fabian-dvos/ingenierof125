from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict


@dataclass(frozen=True, slots=True)
class RuleConfig:
    version: str
    comms_throttle_s: float = 12.0
    event_cooldown_s: Dict[str, float] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)

    def threshold(self, name: str, default: float) -> float:
        v = self.thresholds.get(name)
        return float(default if v is None else v)

    def cooldown(self, key: str, default: float) -> float:
        v = self.event_cooldown_s.get(key)
        return float(default if v is None else v)

    def override(self, *, throttle_s: float | None = None) -> "RuleConfig":
        if throttle_s is None or throttle_s <= 0:
            return self
        return replace(self, comms_throttle_s=float(throttle_s))
