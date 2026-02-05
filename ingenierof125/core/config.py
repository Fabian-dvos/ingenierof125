from __future__ import annotations

import os
from dataclasses import dataclass, replace


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or v.strip() == "" else v.strip()


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class AppConfig:
    udp_host: str = "0.0.0.0"
    udp_port: int = 20777

    packet_format: int = 2025
    game_year: int = 25

    queue_maxsize: int = 2048

    log_level: str = "INFO"
    log_dir: str = "logs"
    log_file: str = "ingenierof125.log"

    # recording / replay
    record_enabled: bool = False
    record_dir: str = "recordings"
    replay_path: str | None = None
    replay_speed: float = 1.0
    replay_no_sleep: bool = False

    @staticmethod
    def from_env() -> "AppConfig":
        return AppConfig(
            udp_host=_env("ING_UDP_HOST", "0.0.0.0"),
            udp_port=_env_int("ING_UDP_PORT", 20777),
            packet_format=_env_int("ING_PACKET_FORMAT", 2025),
            game_year=_env_int("ING_GAME_YEAR", 25),
            queue_maxsize=_env_int("ING_QUEUE_MAXSIZE", 2048),
            log_level=_env("ING_LOG_LEVEL", "INFO").upper(),
            log_dir=_env("ING_LOG_DIR", "logs"),
            log_file=_env("ING_LOG_FILE", "ingenierof125.log"),
        )

    def override(
        self,
        udp_host: str | None = None,
        udp_port: int | None = None,
        packet_format: int | None = None,
        game_year: int | None = None,
        queue_maxsize: int | None = None,
        log_level: str | None = None,
        record_enabled: bool | None = None,
        record_dir: str | None = None,
        replay_path: str | None = None,
        replay_speed: float | None = None,
        replay_no_sleep: bool | None = None,
    ) -> "AppConfig":
        return replace(
            self,
            udp_host=self.udp_host if udp_host is None else udp_host,
            udp_port=self.udp_port if udp_port is None else udp_port,
            packet_format=self.packet_format if packet_format is None else packet_format,
            game_year=self.game_year if game_year is None else game_year,
            queue_maxsize=self.queue_maxsize if queue_maxsize is None else queue_maxsize,
            log_level=self.log_level if log_level is None else log_level,
            record_enabled=self.record_enabled if record_enabled is None else bool(record_enabled),
            record_dir=self.record_dir if record_dir is None else record_dir,
            replay_path=self.replay_path if replay_path is None else replay_path,
            replay_speed=self.replay_speed if replay_speed is None else float(replay_speed),
            replay_no_sleep=self.replay_no_sleep if replay_no_sleep is None else bool(replay_no_sleep),
        )
