from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _as_int(v: Any, default: int) -> int:
    try:
        x = int(v)
        return x if x > 0 else default
    except Exception:
        return default


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _as_bool(v: Any, default: bool) -> bool:
    try:
        return bool(v)
    except Exception:
        return default


def _as_str(v: Any, default: str) -> str:
    try:
        s = str(v)
        return s if s else default
    except Exception:
        return default


@dataclass(slots=True)
class AppConfig:
    # logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # protocol expectations
    packet_format: int = 2025  # F1 25 UDP "format" (m_packetFormat)

    # mode
    listen: str = "0.0.0.0:20777"
    replay: str = ""
    replay_speed: float = 1.0
    replay_no_sleep: bool = False

    # queues
    queue_maxsize: int = 2048
    dispatch_maxsize: int = 2048

    # recording
    record: bool = False
    record_dir: str = "recordings"

    # observability
    stats_interval: float = 0.0
    state_interval: float = 0.0

    # engine/rules
    no_engine: bool = False
    rules_path: str = "rules/v1.json"
    comm_throttle: float = 0.0

    # supervisor
    no_supervisor: bool = False

    @classmethod
    def from_obj(cls, obj: Any) -> "AppConfig":
        """
        Construye config estable desde argparse.Namespace o cualquier objeto con atributos.
        IMPORTANTE: con dataclass(slots=True) NO usar cls.campo como default (es member_descriptor).
        """
        base = cls()  # << defaults REALES

        get = getattr
        cfg = cls(
            log_level=_as_str(get(obj, "log_level", base.log_level), base.log_level),
            log_dir=_as_str(get(obj, "log_dir", base.log_dir), base.log_dir),

            packet_format=_as_int(get(obj, "packet_format", base.packet_format), base.packet_format),

            listen=_as_str(get(obj, "listen", base.listen), base.listen),
            replay=_as_str(get(obj, "replay", base.replay), base.replay),
            replay_speed=_as_float(get(obj, "replay_speed", base.replay_speed), base.replay_speed),
            replay_no_sleep=_as_bool(get(obj, "replay_no_sleep", base.replay_no_sleep), base.replay_no_sleep),

            queue_maxsize=_as_int(get(obj, "queue_maxsize", base.queue_maxsize), base.queue_maxsize),
            dispatch_maxsize=_as_int(get(obj, "dispatch_maxsize", base.dispatch_maxsize), base.dispatch_maxsize),

            record=_as_bool(get(obj, "record", base.record), base.record),
            record_dir=_as_str(get(obj, "record_dir", base.record_dir), base.record_dir),

            stats_interval=_as_float(get(obj, "stats_interval", base.stats_interval), base.stats_interval),
            state_interval=_as_float(get(obj, "state_interval", base.state_interval), base.state_interval),

            no_engine=_as_bool(get(obj, "no_engine", base.no_engine), base.no_engine),
            rules_path=_as_str(get(obj, "rules_path", base.rules_path), base.rules_path),
            comm_throttle=_as_float(get(obj, "comm_throttle", base.comm_throttle), base.comm_throttle),

            no_supervisor=_as_bool(get(obj, "no_supervisor", base.no_supervisor), base.no_supervisor),
        )

        # saneamientos mínimos
        if cfg.replay_speed <= 0:
            cfg.replay_speed = 1.0
        if cfg.packet_format <= 0:
            cfg.packet_format = 2025

        return cfg
