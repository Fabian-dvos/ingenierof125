from __future__ import annotations

import logging
from dataclasses import dataclass

from ingenierof125.engine.events import Event


@dataclass(slots=True)
class LoggerComms:
    logger_name: str = "ingenierof125.comms"

    def emit(self, ev: Event) -> None:
        log = logging.getLogger(self.logger_name)
        tag = ev.priority.name
        log.info("[%s] %s", tag, ev.text)
