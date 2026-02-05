from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ingenierof125.telemetry.decoders_lite import (
    PlayerDamageLite,
    PlayerLapLite,
    PlayerStatusLite,
    PlayerTelemetryLite,
    SessionLite,
)


@dataclass(slots=True)
class TimedValue:
    t: float = -1.0  # session_time seconds (F1 header)
    ok: bool = False


@dataclass(slots=True)
class SessionState(TimedValue):
    value: Optional[SessionLite] = None


@dataclass(slots=True)
class LapState(TimedValue):
    value: Optional[PlayerLapLite] = None


@dataclass(slots=True)
class StatusState(TimedValue):
    value: Optional[PlayerStatusLite] = None


@dataclass(slots=True)
class TelemetryState(TimedValue):
    value: Optional[PlayerTelemetryLite] = None


@dataclass(slots=True)
class DamageState(TimedValue):
    value: Optional[PlayerDamageLite] = None


@dataclass(slots=True)
class EngineerState:
    # IMPORTANT: default_factory para evitar defaults mutables compartidos
    session: SessionState = field(default_factory=SessionState)
    lap: LapState = field(default_factory=LapState)
    status: StatusState = field(default_factory=StatusState)
    telemetry: TelemetryState = field(default_factory=TelemetryState)
    damage: DamageState = field(default_factory=DamageState)

    latest_session_time: float = -1.0
    player_index: int = 0

    decode_errors: int = 0
