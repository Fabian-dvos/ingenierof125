from __future__ import annotations

import argparse
import asyncio
import inspect
import traceback

from ingenierof125.app import run_app


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ingenierof125")

    ap.add_argument("--log-level", type=str, default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    ap.add_argument("--no-supervisor", action="store_true", help="Disable watchdog/supervisor (dev)")

    # Mode selection
    ap.add_argument("--listen", type=str, default="0.0.0.0:20777", help="host:port UDP (default 0.0.0.0:20777)")
    ap.add_argument("--replay", type=str, default="", help="Path to .ingrec replay file")
    ap.add_argument("--replay-speed", type=float, default=1.0, help="Replay speed multiplier")
    ap.add_argument("--replay-no-sleep", action="store_true", help="Replay as fast as possible (no pacing)")

    # Recording
    ap.add_argument("--record", action="store_true", help="Record UDP into .ingrec")
    ap.add_argument("--record-dir", type=str, default="recordings", help="Directory for recordings")

    # Observability
    ap.add_argument("--stats-interval", type=float, default=0.0, help="Print stats every N seconds (0=off)")
    ap.add_argument("--state-interval", type=float, default=0.0, help="Print state snapshot every N seconds (0=off)")

    # Engine / Rules
    ap.add_argument("--no-engine", action="store_true", help="Disable rules/priority engine")
    ap.add_argument("--rules-path", type=str, default="rules/v1.json", help="Rules JSON path")
    ap.add_argument("--comm-throttle", type=float, default=0.0, help="Override throttle seconds (0=use rules)")

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    # normalizar vacíos
    args.replay = args.replay or ""
    args.listen = args.listen or "0.0.0.0:20777"

    try:
        result = run_app(args)
        if inspect.iscoroutine(result):
            result = asyncio.run(result)
        return int(result or 0)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
