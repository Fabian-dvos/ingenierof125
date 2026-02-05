$ErrorActionPreference = "Stop"

function Write-Utf8([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Set-Content -Path $Path -Value $Text -Encoding utf8
}

if (-not (Test-Path ".git")) { throw "Ejecutá esto en la RAÍZ del repo (donde está .git)." }

# --- FIX replay.py (saca los \" y deja Python válido) ---
Write-Utf8 ".\ingenierof125\ingest\replay.py" @"
from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import BinaryIO, Optional


MAGIC = b"INGREC1`0"
_HEADER = struct.Struct("<8sH")
_RECORD = struct.Struct("<QI")


@dataclass(slots=True)
class ReplayStats:
    sent: int = 0


class PacketReplayer:
    def __init__(self, path: str, speed: float = 1.0, no_sleep: bool = False) -> None:
        self._path = path
        self._speed = max(0.01, float(speed))
        self._no_sleep = bool(no_sleep)
        self._log = logging.getLogger("ingenierof125.replay")
        self._stop = asyncio.Event()
        self.stats = ReplayStats()

    def stop(self) -> None:
        self._stop.set()

    def _open(self) -> BinaryIO:
        f = open(self._path, "rb")
        header = f.read(_HEADER.size)
        if len(header) != _HEADER.size:
            raise ValueError("Replay: header incompleto")
        magic, ver = _HEADER.unpack(header)
        if magic != MAGIC:
            raise ValueError("Replay: magic inválido (no es archivo ingrec)")
        if ver != 1:
            raise ValueError(f"Replay: versión no soportada: {ver}")
        return f

    async def run(self, out_queue: "asyncio.Queue[bytes]") -> None:
        self._log.info("Replaying %s (speed=%.2f no_sleep=%s)", self._path, self._speed, self._no_sleep)

        f: Optional[BinaryIO] = None
        try:
            f = self._open()
            last_ts: int | None = None

            while not self._stop.is_set():
                hdr = f.read(_RECORD.size)
                if not hdr or len(hdr) < _RECORD.size:
                    break

                ts_ns, length = _RECORD.unpack(hdr)
                payload = f.read(length)
                if len(payload) != length:
                    break

                if (not self._no_sleep) and (last_ts is not None):
                    dt_ns = ts_ns - last_ts
                    if dt_ns > 0:
                        await asyncio.sleep((dt_ns / 1e9) / self._speed)
                last_ts = ts_ns

                await out_queue.put(payload)
                self.stats.sent += 1
        finally:
            if f:
                f.close()
            self._log.info("Replay finished: sent=%s", self.stats.sent)
"@

# --- FIX app.py (quita \" y hace fanout correcto: raw -> (recorder + dispatcher)) ---
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
    log = logging.getLogger("ingenierof125")

    # Cola interna para datagramas crudos (solo en modo UDP)
    raw_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)
    # Cola que consume el dispatcher (modo UDP o REPLAY)
    dispatch_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)

    dispatcher = PacketDispatcher(expected_packet_format=cfg.packet_format, expected_game_year=cfg.game_year)
    recorder = PacketRecorder(out_dir=cfg.record_dir, enabled=cfg.record_enabled)

    listener: UdpListener | None = None
    replayer: PacketReplayer | None = None

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(dispatcher.run(dispatch_queue), name="packet-dispatcher"))

    if cfg.record_enabled:
        tasks.append(asyncio.create_task(recorder.run(), name="udp-recorder"))

    if cfg.replay_path:
        log.info("Mode=REPLAY path=%s record=%s", cfg.replay_path, cfg.record_enabled)
        replayer = PacketReplayer(path=cfg.replay_path, speed=cfg.replay_speed, no_sleep=cfg.replay_no_sleep)

        async def _replay_fanout() -> None:
            # En replay, los paquetes van directo a dispatch_queue,
            # pero si record está activo, también los guardamos.
            tmp_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)
            replay_task = asyncio.create_task(replayer.run(tmp_queue), name="udp-replayer-inner")
            try:
                while True:
                    data = await tmp_queue.get()
                    if cfg.record_enabled:
                        recorder.try_enqueue(data)
                    await dispatch_queue.put(data)
            finally:
                replay_task.cancel()

        tasks.append(asyncio.create_task(_replay_fanout(), name="replay-fanout"))

    else:
        log.info("Mode=UDP listen=%s:%s record=%s", cfg.udp_host, cfg.udp_port, cfg.record_enabled)
        listener = UdpListener(cfg.udp_host, cfg.udp_port, raw_queue, drop_when_full=True)
        tasks.append(asyncio.create_task(listener.run(), name="udp-listener"))

        async def _udp_fanout() -> None:
            while True:
                data = await raw_queue.get()
                if cfg.record_enabled:
                    recorder.try_enqueue(data)
                await dispatch_queue.put(data)

        tasks.append(asyncio.create_task(_udp_fanout(), name="udp-fanout"))

    try:
        await asyncio.gather(*tasks)
    finally:
        log.info("Shutting down...")
        dispatcher.stop()
        recorder.stop()
        if listener:
            listener.stop()
        if replayer:
            replayer.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
"@

Write-Host "OK: app.py y replay.py corregidos." -ForegroundColor Green
