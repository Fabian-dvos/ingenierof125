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
    p.add_argument("--stats-interval", type=float, default=None, help="Segundos entre logs de salud (default: 2.0)")
    p.add_argument("--state-interval", type=float, default=None, help="Segundos entre snapshots de estado (default: 1.0)")

    ap.add_argument("--no-engine", action="store_true", help="Disable rules/priority engine")
    ap.add_argument("--rules-path", type=str, default="rules/v1.json", help="Rules JSON path")
    ap.add_argument("--comm-throttle", type=float, default=0.0, help="Override throttle seconds (0=rules)")

    p.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Nivel de log (default: INFO)",
    )

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
        stats_interval_s=args.stats_interval,
        state_interval_s=args.state_interval,
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
