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
