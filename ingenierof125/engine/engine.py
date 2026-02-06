from __future__ import annotations

from dataclasses import dataclass

from ingenierof125.comms.logger_sink import LoggerComms
from ingenierof125.engine.detector import EventDetector
from ingenierof125.engine.priority import PriorityManager
from ingenierof125.rules.model import RuleConfig


@dataclass(slots=True)
class EngineerEngine:
    cfg: RuleConfig
    comms: LoggerComms
    detector: EventDetector
    pm: PriorityManager
    last_t: float = -1e9

    @classmethod
    def create(cls, cfg: RuleConfig, comms: LoggerComms) -> "EngineerEngine":
        return cls(
            cfg=cfg,
            comms=comms,
            detector=EventDetector(cfg),
            pm=PriorityManager(throttle_s=cfg.comms_throttle_s),
        )

    def tick(self, state, t: float) -> None:
        # evita spam si el clock no avanza
        if t <= self.last_t:
            return
        self.last_t = t

        events = self.detector.detect(state)
        ev = self.pm.select(events, t)
        if ev is None:
            return

        self.comms.emit(ev)
        self.pm.mark_emitted(ev, t)
