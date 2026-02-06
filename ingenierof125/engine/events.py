from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Any


class Priority(IntEnum):
    IMMEDIATE_RISK = 100
    STRATEGY_OPPORTUNITY = 80
    MANAGEMENT = 60
    CONTEXT = 40
    INFO = 20


@dataclass(slots=True)
class Event:
    key: str
    priority: Priority
    score: float
    urgency: int  # 1 = ignora throttling
    text: str
    cooldown_s: float = 15.0
    data: Dict[str, Any] = field(default_factory=dict)
