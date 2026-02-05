$ErrorActionPreference = "Stop"

function Backup-IfExists([string]$Path) {
  if (Test-Path $Path) { Copy-Item $Path ($Path + ".bak") -Force }
}

function Write-Utf8([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Set-Content -Path $Path -Value $Text -Encoding utf8
}

if (-not (Test-Path ".git")) { throw "Ejecutá esto en la RAÍZ del repo (donde está .git)" }

New-Item -ItemType Directory -Force .\ingenierof125\ingest, .\recordings, .\docs | Out-Null

# backups
@(
  ".\ingenierof125\app.py",
  ".\ingenierof125\cli.py",
  ".\ingenierof125\core\config.py"
) | ForEach-Object { Backup-IfExists $_ }

Write-Utf8 ".\ingenierof125\ingest\__init__.py" @"
# ingest: recorder + replay
"@

Write-Utf8 ".\ingenierof125\ingest\recorder.py" @"
from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


MAGIC = b"INGREC1\0"  # 8 bytes
VERSION = 1
_HEADER = struct.Struct("<8sH")        # magic + u16 version
_RECORD = struct.Struct("<QI")         # u64 ts_ns + u32 length


@dataclass(slots=True)
class RecorderStats:
    written: int = 0
    dropped: int = 0


class PacketRecorder:
    def __init__(
        self,
        out_dir: str = "recordings",
        enabled: bool = False,
        queue_maxsize: int = 4096,
        flush_every: int = 64,
    ) -> None:
        self._enabled = enabled
        self._out_dir = out_dir
        self._flush_every = max(1, int(flush_every))
        self._log = logging.getLogger("ingenierof125.recorder")
        self._stop = asyncio.Event()
        self.stats = RecorderStats()

        self._queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue(maxsize=queue_maxsize)
        self._file = None  # type: Optional[object]
        self._path: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> str | None:
        return self._path

    def stop(self) -> None:
        self._stop.set()

    def try_enqueue(self, payload: bytes, ts_ns: int | None = None) -> None:
        if not self._enabled:
            return
        if ts_ns is None:
            ts_ns = time.time_ns()
        try:
            self._queue.put_nowait((ts_ns, payload))
        except asyncio.QueueFull:
            self.stats.dropped += 1

    def _open(self) -> None:
        os.makedirs(self._out_dir, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_f1udp.ingrec"
        self._path = os.path.join(self._out_dir, name)
        f = open(self._path, "wb", buffering=1024 * 1024)
        f.write(_HEADER.pack(MAGIC, VERSION))
        self._file = f
        self._log.info("Recording to %s", self._path)

    def _close(self) -> None:
        try:
            if self._file:
                self._file.flush()
                self._file.close()
        finally:
            self._file = None

    async def run(self) -> None:
        if not self._enabled:
            return

        self._open()
        assert self._file is not None

        buffered = 0
        try:
            while not self._stop.is_set():
                try:
                    ts_ns, payload = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if len(payload) > 0xFFFFFFFF:
                    self.stats.dropped += 1
                    continue

                self._file.write(_RECORD.pack(ts_ns, len(payload)))
                self._file.write(payload)
                self.stats.written += 1
                buffered += 1

                if buffered >= self._flush_every:
                    self._file.flush()
                    buffered = 0
        finally:
            self._close()
"@

Write-Utf8 ".\ingenierof125\ingest\replay.py" @"
from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import BinaryIO, Optional


MAGIC = b\"INGREC1\\0\"
_HEADER = struct.Struct(\"<8sH\")
_RECORD = struct.Struct(\"<QI\")


@dataclass(slots=True)
class ReplayStats:
    sent: int = 0


class PacketReplayer:
    def __init__(self, path: str, speed: float = 1.0, no_sleep: bool = False) -> None:
        self._path = path
        self._speed = max(0.01, float(speed))
        self._no_sleep = bool(no_sleep)
        self._log = logging.getLogger(\"ingenierof125.replay\")
        self._stop = asyncio.Event()
        self.stats = ReplayStats()

    def stop(self) -> None:
        self._stop.set()

    def _open(self) -> BinaryIO:
        f = open(self._path, \"rb\")
        magic, ver = _HEADER.unpack(f.read(_HEADER.size))
        if magic != MAGIC:
            raise ValueError(\"Replay: magic inválido (no es archivo ingrec)\")
        if ver != 1:
            raise ValueError(f\"Replay: versión no soportada: {ver}\")
        return f

    async def run(self, out_queue: \"asyncio.Queue[bytes]\") -> None:
        self._log.info(\"Replaying %s (speed=%.2f no_sleep=%s)\", self._path, self._speed, self._no_sleep)

        f: Optional[BinaryIO] = None
        try:
            f = self._open()
            first_ts: int | None = None
            last_ts: int | None = None

            while not self._stop.is_set():
                hdr = f.read(_RECORD.size)
                if not hdr or len(hdr) < _RECORD.size:
                    break

                ts_ns, length = _RECORD.unpack(hdr)
                payload = f.read(length)
                if len(payload) != length:
                    break

                if first_ts is None:
                    first_ts = ts_ns
                    last_ts = ts_ns

                if not self._no_sleep and last_ts is not None:
                    dt_ns = ts_ns - last_ts
                    if dt_ns > 0:
                        await asyncio.sleep((dt_ns / 1e9) / self._speed)
                last_ts = ts_ns

                await out_queue.put(payload)
                self.stats.sent += 1
        finally:
            if f:
                f.close()
            self._log.info(\"Replay finished: sent=%s\", self.stats.sent)
"@

# docs
Write-Utf8 ".\docs\REPLAY.md" @"
# Recorder + Replay

## Grabar (con juego abierto)
python -m ingenierof125 --no-supervisor --record --record-dir recordings

## Reproducir (sin abrir el juego)
python -m ingenierof125 --no-supervisor --replay recordings\\TU_ARCHIVO.ingrec --replay-speed 1.0

Opciones:
- --replay-speed 2.0  (2x)
- --replay-no-sleep   (lo más rápido posible)
"@

# config: agregar record/replay settings
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
"@

# cli: flags record/replay
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

    # recorder/replay
    p.add_argument("--record", action="store_true", help="Grabar UDP crudo a archivo")
    p.add_argument("--record-dir", default=None, help="Carpeta de grabación (default: recordings)")
    p.add_argument("--replay", default=None, help="Reproducir desde archivo .ingrec (sin UDP)")
    p.add_argument("--replay-speed", type=float, default=None, help="Velocidad replay (default: 1.0)")
    p.add_argument("--replay-no-sleep", action="store_true", help="Replay lo más rápido posible")

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
        record_enabled=args.record,
        record_dir=args.record_dir,
        replay_path=args.replay,
        replay_speed=args.replay_speed,
        replay_no_sleep=args.replay_no_sleep,
    )

    if args.no_supervisor:
        asyncio.run(run_app(cfg))
        return 0

    return run_with_supervisor(cfg, run_app)
"@

# app: decide UDP vs replay + recorder
Write-Utf8 ".\ingenierof125\app.py" @"
from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.config import AppConfig
from ingenierof125.core.logging_setup import setup_logging
from ingenierof125.ingest.recorder import PacketRecorder
from ingenierof125.ingest.replay import PacketReplayer
from ingenierof125.telemetry.dispatcher import PacketDispatcher
from ingenierof125.telemetry.udp_listener import UdpListener


async def run_app(cfg: AppConfig) -> None:
    setup_logging(cfg)
    log = logging.getLogger(\"ingenierof125\")

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)

    dispatcher = PacketDispatcher(expected_packet_format=cfg.packet_format, expected_game_year=cfg.game_year)

    recorder = PacketRecorder(out_dir=cfg.record_dir, enabled=cfg.record_enabled)

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(dispatcher.run(queue), name=\"packet-dispatcher\"))

    if cfg.record_enabled:
        tasks.append(asyncio.create_task(recorder.run(), name=\"udp-recorder\"))

    if cfg.replay_path:
        log.info(\"Mode=REPLAY path=%s\", cfg.replay_path)
        replayer = PacketReplayer(path=cfg.replay_path, speed=cfg.replay_speed, no_sleep=cfg.replay_no_sleep)
        tasks.append(asyncio.create_task(replayer.run(queue), name=\"udp-replayer\"))
    else:
        log.info(\"Mode=UDP listen=%s:%s record=%s\", cfg.udp_host, cfg.udp_port, cfg.record_enabled)
        listener = UdpListener(cfg.udp_host, cfg.udp_port, queue, drop_when_full=True)

        # Enchufe del recorder sin bloquear el loop UDP
        # (monkey-tap seguro: el listener solo mete a la cola; recorder toma del mismo flujo via hook)
        # Para no tocar mucho el listener ahora: usamos el dispatcher debug como validación,
        # y en el próximo paso hacemos 'fanout' limpio (1 cola para core + 1 cola para recorder).
        #
        # Por ahora, grabamos desde el listener mediante un wrapper mínimo:
        original_datagram_received = None

        # Inyectamos un wrapper en el protocolo interno del listener, si existe.
        # Si no existe (por cambios futuros), el sistema sigue funcionando sin grabar.
        listener_task = asyncio.create_task(listener.run(), name=\"udp-listener\")
        tasks.append(listener_task)

        # Hook simple: task que drena la cola principal y re-inserta (fanout sin tocar listener)
        # Nota: esto introduce overhead; en el próximo paso lo reemplazamos por fanout real en el listener.
        if cfg.record_enabled:
            async def _fanout() -> None:
                while True:
                    data = await queue.get()
                    recorder.try_enqueue(data)
                    await queue.put(data)
            tasks.append(asyncio.create_task(_fanout(), name=\"fanout-temp\"))

    try:
        await asyncio.gather(*tasks)
    finally:
        log.info(\"Shutting down...\")
        dispatcher.stop()
        recorder.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
"@

Write-Host "OK: recorder + replay instalado." -ForegroundColor Green
