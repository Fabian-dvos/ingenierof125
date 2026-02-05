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
