from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ingenierof125.engine.events import Event


@dataclass(slots=True)
class PriorityManager:
    throttle_s: float
    last_emit_t: float = -1e9
    last_emit_by_key: Dict[str, float] = field(default_factory=dict)
    last_score_by_key: Dict[str, float] = field(default_factory=dict)

    def _cooldown_ok(self, ev: Event, t: float) -> bool:
        last = self.last_emit_by_key.get(ev.key, -1e9)
        if (t - last) >= float(ev.cooldown_s):
            return True
        # deja pasar si subió score y es urgencia
        prev = self.last_score_by_key.get(ev.key, -1e9)
        return ev.urgency >= 1 and ev.score > prev

    def select(self, events: list[Event], t: float) -> Optional[Event]:
        if not events:
            return None

        # ordenar por impacto
        events = sorted(events, key=lambda e: (int(e.priority), float(e.score)), reverse=True)

        # urgentes primero (bypassean throttle)
        urgent = [e for e in events if e.urgency >= 1 and self._cooldown_ok(e, t)]
        if urgent:
            return urgent[0]

        # throttle normal
        if (t - self.last_emit_t) < float(self.throttle_s):
            return None

        # mejor evento no-urgente que pase cooldown
        for ev in events:
            if self._cooldown_ok(ev, t):
                return ev

        return None

    def mark_emitted(self, ev: Event, t: float) -> None:
        self.last_emit_t = t
        self.last_emit_by_key[ev.key] = t
        self.last_score_by_key[ev.key] = float(ev.score)
