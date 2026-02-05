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
