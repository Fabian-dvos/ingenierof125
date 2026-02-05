$ErrorActionPreference = "Stop"

function Backup-IfExists([string]$Path) {
  if (Test-Path $Path) {
    Copy-Item $Path ($Path + ".bak") -Force
  }
}

function Write-Utf8([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Set-Content -Path $Path -Value $Text -Encoding utf8
}

# backups (por si querés comparar)
$targets = @(
  ".\ingenierof125\app.py",
  ".\ingenierof125\cli.py",
  ".\ingenierof125\core\config.py",
  ".\ingenierof125\telemetry\udp_listener.py",
  ".\ingenierof125\telemetry\dispatcher.py",
  ".\apply_clipboard_patch.ps1"
)
$targets | ForEach-Object { Backup-IfExists $_ }

# stats
Write-Utf8 ".\ingenierof125\core\stats.py" @"
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeStats:
    # UDP layer
    udp_received: int = 0
    udp_dropped_queue: int = 0

    # Processed
    dispatched_received: int = 0
    dropped_bad_header: int = 0
    dropped_format_mismatch: int = 0

    by_packet_id: dict[int, int] = field(default_factory=dict)


class StatsReporter:
    def __init__(self, stats: RuntimeStats, queue: "asyncio.Queue[bytes]", interval_s: float = 2.0) -> None:
        self._stats = stats
        self._queue = queue
        self._interval_s = max(0.5, float(interval_s))
        self._stop = asyncio.Event()
        self._log = logging.getLogger("ingenierof125.stats")

        self._last_ts = time.monotonic()
        self._last_udp = 0

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self._interval_s)

            now = time.monotonic()
            dt = max(1e-6, now - self._last_ts)
            delta = self._stats.udp_received - self._last_udp
            pps = delta / dt

            ids = dict(sorted(self._stats.by_packet_id.items()))
            qsize = self._queue.qsize()
            qmax = self._queue.maxsize

            self._log.info(
                "udp_rx=%s (%.1f pkt/s) q=%s/%s dropQ=%s ok=%s dropHdr=%s dropFmt=%s ids=%s",
                self._stats.udp_received,
                pps,
                qsize,
                qmax,
                self._stats.udp_dropped_queue,
                self._stats.dispatched_received,
                self._stats.dropped_bad_header,
                self._stats.dropped_format_mismatch,
                ids,
            )

            self._last_ts = now
            self._last_udp = self._stats.udp_received
"@

# config (agrega stats_interval_s y env float)
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


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v.strip())
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
    stats_interval_s: float = 2.0

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
            stats_interval_s=_env_float("ING_STATS_INTERVAL_S", 2.0),
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
        stats_interval_s: float | None = None,
        log_level: str | None = None,
    ) -> "AppConfig":
        return replace(
            self,
            udp_host=self.udp_host if udp_host is None else udp_host,
            udp_port=self.udp_port if udp_port is None else udp_port,
            packet_format=self.packet_format if packet_format is None else packet_format,
            game_year=self.game_year if game_year is None else game_year,
            queue_maxsize=self.queue_maxsize if queue_maxsize is None else queue_maxsize,
            stats_interval_s=self.stats_interval_s if stats_interval_s is None else float(stats_interval_s),
            log_level=self.log_level if log_level is None else log_level,
        )
"@

# cli (agrega --stats-interval)
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
    p.add_argument("--stats-interval", type=float, default=None, help="Segundos entre stats (default: 2.0)")
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
        stats_interval_s=args.stats_interval,
        log_level=args.log_level,
    )

    if args.no_supervisor:
        asyncio.run(run_app(cfg))
        return 0

    return run_with_supervisor(cfg, run_app)
"@

# udp_listener (cuenta rx y drops)
Write-Utf8 ".\ingenierof125\telemetry\udp_listener.py" @"
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ingenierof125.core.stats import RuntimeStats


@dataclass(slots=True)
class _UdpProtocol(asyncio.DatagramProtocol):
    out_queue: "asyncio.Queue[bytes]"
    drop_when_full: bool
    log: logging.Logger
    stats: RuntimeStats

    def datagram_received(self, data: bytes, addr) -> None:  # type: ignore[override]
        self.stats.udp_received += 1

        if self.drop_when_full and self.out_queue.full():
            self.stats.udp_dropped_queue += 1
            return

        try:
            self.out_queue.put_nowait(data)
        except asyncio.QueueFull:
            self.stats.udp_dropped_queue += 1


class UdpListener:
    def __init__(
        self,
        host: str,
        port: int,
        out_queue: "asyncio.Queue[bytes]",
        drop_when_full: bool = True,
        stats: RuntimeStats | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._out_queue = out_queue
        self._drop_when_full = drop_when_full
        self._log = logging.getLogger("ingenierof125.udp")
        self._stop = asyncio.Event()
        self._transport: asyncio.DatagramTransport | None = None
        self._stats = stats or RuntimeStats()

    def stop(self) -> None:
        self._stop.set()
        if self._transport is not None:
            self._transport.close()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        protocol = _UdpProtocol(self._out_queue, self._drop_when_full, self._log, self._stats)
        transport, _ = await loop.create_datagram_endpoint(lambda: protocol, local_addr=(self._host, self._port))
        self._transport = transport  # type: ignore[assignment]
        self._log.info("Listening UDP on %s:%s", self._host, self._port)

        try:
            while not self._stop.is_set():
                await asyncio.sleep(1.0)
        finally:
            self.stop()
"@

# dispatcher (cuenta por packet_id + drops)
Write-Utf8 ".\ingenierof125\telemetry\dispatcher.py" @"
from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.stats import RuntimeStats
from ingenierof125.telemetry.protocol import PacketHeader


class PacketDispatcher:
    def __init__(self, expected_packet_format: int, expected_game_year: int, stats: RuntimeStats | None = None) -> None:
        self._log = logging.getLogger("ingenierof125.dispatcher")
        self._stop = asyncio.Event()
        self._expected_packet_format = expected_packet_format
        self._expected_game_year = expected_game_year
        self._stats = stats or RuntimeStats()

    def stop(self) -> None:
        self._stop.set()

    async def run(self, in_queue: "asyncio.Queue[bytes]") -> None:
        self._log.info("Dispatcher running")
        while not self._stop.is_set():
            try:
                data = await asyncio.wait_for(in_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            self._stats.dispatched_received += 1

            hdr = PacketHeader.try_parse(data)
            if hdr is None:
                self._stats.dropped_bad_header += 1
                continue

            if hdr.packet_format != self._expected_packet_format or hdr.game_year != self._expected_game_year:
                self._stats.dropped_format_mismatch += 1
                continue

            self._stats.by_packet_id[hdr.packet_id] = self._stats.by_packet_id.get(hdr.packet_id, 0) + 1

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

# app (lanza StatsReporter)
Write-Utf8 ".\ingenierof125\app.py" @"
from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.config import AppConfig
from ingenierof125.core.logging_setup import setup_logging
from ingenierof125.core.stats import RuntimeStats, StatsReporter
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
    stats = RuntimeStats()

    listener = UdpListener(cfg.udp_host, cfg.udp_port, queue, drop_when_full=True, stats=stats)
    dispatcher = PacketDispatcher(expected_packet_format=cfg.packet_format, expected_game_year=cfg.game_year, stats=stats)
    reporter = StatsReporter(stats=stats, queue=queue, interval_s=cfg.stats_interval_s)

    t1 = asyncio.create_task(listener.run(), name="udp-listener")
    t2 = asyncio.create_task(dispatcher.run(queue), name="packet-dispatcher")
    t3 = asyncio.create_task(reporter.run(), name="stats-reporter")

    try:
        await asyncio.gather(t1, t2, t3)
    finally:
        log.info("Shutting down...")
        reporter.stop()
        dispatcher.stop()
        listener.stop()
        for t in (t1, t2, t3):
            t.cancel()
        await asyncio.gather(t1, t2, t3, return_exceptions=True)
"@

# aplica patch helper arreglado (no miente)
Write-Utf8 ".\apply_clipboard_patch.ps1" @"
param([switch]$Reverse)

$ErrorActionPreference = "Stop"

$raw = Get-Clipboard -Raw
$raw = $raw -replace "`r", ""

$lines = $raw -split "`n" | Where-Object { $_ -notmatch '^\s*```' }
$first = $lines | Select-String -Pattern '^diff --git ' | Select-Object -First 1
if (-not $first) { throw "No encontré 'diff --git' en el portapapeles. Copiá el patch completo." }

$start = $first.LineNumber - 1
$patch = ($lines[$start..($lines.Length-1)] -join "`n") + "`n"

if ($Reverse) { $patch | git apply -R --whitespace=fix }
else { $patch | git apply --whitespace=fix }

if ($LASTEXITCODE -ne 0) { throw "git apply falló (exit=$LASTEXITCODE). El patch NO se aplicó." }

Write-Host "OK: patch aplicado." -ForegroundColor Green
"@

Write-Host "OK: stats + health logs instalados." -ForegroundColor Green
