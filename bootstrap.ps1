$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) {
  throw "Ejecutá esto en la RAÍZ del repo (donde existe la carpeta .git)."
}

function Write-Utf8([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Set-Content -Path $Path -Value $Text -Encoding utf8
}

# Estructura
New-Item -ItemType Directory -Force `
  .\ingenierof125, .\ingenierof125\core, .\ingenierof125\telemetry, .\scripts, .\docs, .\tests | Out-Null

# Paquete
Write-Utf8 ".\ingenierof125\__init__.py" @"
__version__ = "0.1.0"
"@

Write-Utf8 ".\ingenierof125\__main__.py" @"
from __future__ import annotations
from ingenierof125.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
"@

Write-Utf8 ".\ingenierof125\cli.py" @"
from __future__ import annotations

import argparse
import asyncio

from ingenierof125.app import run_app
from ingenierof125.core.config import AppConfig
from ingenierof125.core.supervisor import run_with_supervisor


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingenierof125", add_help=True)
    p.add_argument("--udp-host", default=None, help="Host UDP (default: 0.0.0.0)")
    p.add_argument("--udp-port", type=int, default=None, help="Puerto UDP (default: 20777)")
    p.add_argument("--packet-format", type=int, default=None, help="m_packetFormat esperado (default: 2025)")
    p.add_argument("--game-year", type=int, default=None, help="m_gameYear esperado (default: 25)")
    p.add_argument("--queue-maxsize", type=int, default=None, help="Tamaño de cola (default: 2048)")
    p.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Nivel de log (default: INFO)",
    )
    p.add_argument("--no-supervisor", action="store_true", help="Ejecutar sin auto-restart")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    cfg = AppConfig.from_env().override(
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        packet_format=args.packet_format,
        game_year=args.game_year,
        queue_maxsize=args.queue_maxsize,
        log_level=args.log_level,
    )

    if args.no_supervisor:
        asyncio.run(run_app(cfg))
        return 0

    return run_with_supervisor(cfg, run_app)
"@

Write-Utf8 ".\ingenierof125\app.py" @"
from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.config import AppConfig
from ingenierof125.core.logging_setup import setup_logging
from ingenierof125.telemetry.dispatcher import PacketDispatcher
from ingenierof125.telemetry.udp_listener import UdpListener


async def run_app(cfg: AppConfig) -> None:
    setup_logging(cfg)
    log = logging.getLogger("ingenierof125")
    log.info(
        "Starting udp=%s:%s format=%s year=%s",
        cfg.udp_host, cfg.udp_port, cfg.packet_format, cfg.game_year
    )

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)

    listener = UdpListener(cfg.udp_host, cfg.udp_port, queue, drop_when_full=True)
    dispatcher = PacketDispatcher(expected_packet_format=cfg.packet_format, expected_game_year=cfg.game_year)

    t1 = asyncio.create_task(listener.run(), name="udp-listener")
    t2 = asyncio.create_task(dispatcher.run(queue), name="packet-dispatcher")

    try:
        await asyncio.gather(t1, t2)
    finally:
        log.info("Shutting down...")
        dispatcher.stop()
        listener.stop()
        for t in (t1, t2):
            t.cancel()
        await asyncio.gather(t1, t2, return_exceptions=True)
"@

# Core
Write-Utf8 ".\ingenierof125\core\__init__.py" @"
# core package
"@

Write-Utf8 ".\ingenierof125\core\config.py" @"
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

    # F1 25 expected header fields
    packet_format: int = 2025
    game_year: int = 25

    queue_maxsize: int = 2048

    log_level: str = "INFO"
    log_dir: str = "logs"
    log_file: str = "ingenierof125.log"

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
    ) -> "AppConfig":
        return replace(
            self,
            udp_host=self.udp_host if udp_host is None else udp_host,
            udp_port=self.udp_port if udp_port is None else udp_port,
            packet_format=self.packet_format if packet_format is None else packet_format,
            game_year=self.game_year if game_year is None else game_year,
            queue_maxsize=self.queue_maxsize if queue_maxsize is None else queue_maxsize,
            log_level=self.log_level if log_level is None else log_level,
        )
"@

Write-Utf8 ".\ingenierof125\core\logging_setup.py" @"
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from ingenierof125.core.config import AppConfig


def setup_logging(cfg: AppConfig) -> None:
    os.makedirs(cfg.log_dir, exist_ok=True)
    log_path = os.path.join(cfg.log_dir, cfg.log_file)

    level = getattr(logging, cfg.log_level, logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    for h in list(root.handlers):
        root.removeHandler(h)

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)

    fh = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    root.addHandler(ch)
    root.addHandler(fh)
"@

Write-Utf8 ".\ingenierof125\core\supervisor.py" @"
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from ingenierof125.core.config import AppConfig
from ingenierof125.core.logging_setup import setup_logging


def run_with_supervisor(cfg: AppConfig, runner: Callable[[AppConfig], Awaitable[None]]) -> int:
    setup_logging(cfg)
    log = logging.getLogger("ingenierof125.supervisor")

    backoff = 0.5
    while True:
        try:
            log.info("Launching app (supervised)")
            asyncio.run(runner(cfg))
            log.info("Exited normally")
            return 0
        except KeyboardInterrupt:
            log.info("Interrupted by user")
            return 0
        except Exception:
            log.exception("Crashed; restarting")
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
"@

# Telemetry
Write-Utf8 ".\ingenierof125\telemetry\__init__.py" @"
# telemetry package
"@

Write-Utf8 ".\ingenierof125\telemetry\protocol.py" @"
from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PacketHeader:
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int

    # F1 25 header: 29 bytes, little-endian, packed
    _STRUCT = struct.Struct("<HBBBBBQfIIBB")

    @staticmethod
    def try_parse(data: bytes) -> "PacketHeader | None":
        if len(data) < PacketHeader._STRUCT.size:
            return None
        try:
            pf, gy, gmaj, gmin, pver, pid, suid, st, frame, oframe, pci, spci = PacketHeader._STRUCT.unpack_from(data, 0)
            return PacketHeader(pf, gy, gmaj, gmin, pver, pid, suid, st, frame, oframe, pci, spci)
        except Exception:
            return None
"@

Write-Utf8 ".\ingenierof125\telemetry\udp_listener.py" @"
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass


@dataclass(slots=True)
class _UdpProtocol(asyncio.DatagramProtocol):
    out_queue: "asyncio.Queue[bytes]"
    drop_when_full: bool
    log: logging.Logger
    dropped: int = 0

    def datagram_received(self, data: bytes, addr) -> None:  # type: ignore[override]
        if self.drop_when_full and self.out_queue.full():
            self.dropped += 1
            return
        try:
            self.out_queue.put_nowait(data)
        except asyncio.QueueFull:
            self.dropped += 1


class UdpListener:
    def __init__(self, host: str, port: int, out_queue: "asyncio.Queue[bytes]", drop_when_full: bool = True) -> None:
        self._host = host
        self._port = port
        self._out_queue = out_queue
        self._drop_when_full = drop_when_full
        self._log = logging.getLogger("ingenierof125.udp")
        self._stop = asyncio.Event()
        self._transport: asyncio.DatagramTransport | None = None

    def stop(self) -> None:
        self._stop.set()
        if self._transport is not None:
            self._transport.close()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        protocol = _UdpProtocol(self._out_queue, self._drop_when_full, self._log)
        transport, _ = await loop.create_datagram_endpoint(lambda: protocol, local_addr=(self._host, self._port))
        self._transport = transport  # type: ignore[assignment]
        self._log.info("Listening UDP on %s:%s", self._host, self._port)

        try:
            while not self._stop.is_set():
                await asyncio.sleep(1.0)
        finally:
            self.stop()
"@

Write-Utf8 ".\ingenierof125\telemetry\dispatcher.py" @"
from __future__ import annotations

import asyncio
import logging

from ingenierof125.telemetry.protocol import PacketHeader


class PacketDispatcher:
    def __init__(self, expected_packet_format: int, expected_game_year: int) -> None:
        self._log = logging.getLogger("ingenierof125.dispatcher")
        self._stop = asyncio.Event()
        self._expected_packet_format = expected_packet_format
        self._expected_game_year = expected_game_year

        self.received = 0
        self.dropped_bad_header = 0
        self.dropped_format_mismatch = 0

    def stop(self) -> None:
        self._stop.set()

    async def run(self, in_queue: "asyncio.Queue[bytes]") -> None:
        self._log.info("Dispatcher running")
        while not self._stop.is_set():
            try:
                data = await asyncio.wait_for(in_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            self.received += 1

            hdr = PacketHeader.try_parse(data)
            if hdr is None:
                self.dropped_bad_header += 1
                continue

            if hdr.packet_format != self._expected_packet_format or hdr.game_year != self._expected_game_year:
                self.dropped_format_mismatch += 1
                continue

            if self._log.isEnabledFor(logging.DEBUG):
                self._log.debug(
                    "id=%s ver=%s sess=%s t=%.3f frame=%s len=%s",
                    hdr.packet_id,
                    hdr.packet_version,
                    hdr.session_uid,
                    hdr.session_time,
                    hdr.frame_identifier,
                    len(data),
                )
"@

# Script de ejecución
Write-Utf8 ".\scripts\run_dev.ps1" @"
$ErrorActionPreference = "Stop"
Write-Host "Running (Ctrl+C para salir)..." -ForegroundColor Green
python -m ingenierof125 --no-supervisor --log-level DEBUG
"@

# Doc mini
Write-Utf8 ".\docs\GAME_SETTINGS.md" @"
# F1 25 - Ajustes UDP (mínimo)
- UDP Telemetry: On
- UDP IP Address: 127.0.0.1 (si corrés en la misma PC)
- UDP Port: 20777
- UDP Format: 2025
"@

Write-Host "OK: archivos y código creados." -ForegroundColor Green
