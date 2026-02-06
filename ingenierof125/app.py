from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.config import AppConfig
from ingenierof125.core.logging_setup import setup_logging
from ingenierof125.core.stats import RuntimeStats, StatsReporter
from ingenierof125.ingest.recorder import PacketRecorder
from ingenierof125.ingest.replay import PacketReplayer
from ingenierof125.state.manager import StateManager
from ingenierof125.telemetry.dispatcher import PacketDispatcher
from ingenierof125.telemetry.udp_listener import UdpListener
from ingenierof125.engine.engine import EngineerEngine
from ingenierof125.rules.load import load_rules, default_rules_path
from ingenierof125.comms.logger_sink import LoggerComms



async def run_app(cfg: AppConfig) -> None:
    setup_logging(cfg)
    log = logging.getLogger("ingenierof125")
    state_log = logging.getLogger("ingenierof125.state_snapshot")

    raw_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)
    dispatch_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)

    stats = RuntimeStats()
    state = StateManager()

    engine_task = None
    engine = None
    try:
        if (not getattr(args, 'no_engine', False)) and float(getattr(args, 'state_interval', 0) or 0) > 0:
            rules_path = getattr(args, 'rules_path', None) or str(default_rules_path())
            cfg = load_rules(rules_path)
            override = float(getattr(args, 'comm_throttle', 0) or 0)
            cfg = cfg.override(throttle_s=override)
            engine = EngineerEngine.create(cfg, LoggerComms())
            engine_task = asyncio.create_task(_engine_loop(state_mgr, engine, float(getattr(args, 'state_interval'))))
    except Exception:
        import logging
        logging.getLogger('ingenierof125').exception('Engine init failed (continuing without engine)')


    dispatcher = PacketDispatcher(
        expected_packet_format=cfg.packet_format,
        expected_game_year=cfg.game_year,
        stats=stats,
        state_manager=state,
    )
    recorder = PacketRecorder(out_dir=cfg.record_dir, enabled=cfg.record_enabled)
    reporter = StatsReporter(
        stats=stats,
        interval_s=cfg.stats_interval_s,
        raw_queue=None if cfg.replay_path else raw_queue,
        dispatch_queue=dispatch_queue,
        recorder=recorder,
    )

    async def _state_reporter() -> None:
        # snapshot 1 vez por segundo (configurable)
        while True:
            await asyncio.sleep(cfg.state_interval_s)
            # evitamos spam si todavía no hay tiempo válido
            if state.state.latest_session_time < 0:
                continue
            state_log.info(state.format_one_line())

    listener: UdpListener | None = None
    replayer: PacketReplayer | None = None

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(dispatcher.run(dispatch_queue), name="packet-dispatcher"))
    tasks.append(asyncio.create_task(reporter.run(), name="stats-reporter"))
    tasks.append(asyncio.create_task(_state_reporter(), name="state-reporter"))

    if cfg.record_enabled:
        tasks.append(asyncio.create_task(recorder.run(), name="udp-recorder"))

    if cfg.replay_path:
        log.info("Mode=REPLAY path=%s record=%s", cfg.replay_path, cfg.record_enabled)
        replayer = PacketReplayer(path=cfg.replay_path, speed=cfg.replay_speed, no_sleep=cfg.replay_no_sleep)

        async def _replay_fanout() -> None:
            tmp_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=cfg.queue_maxsize)
            replay_task = asyncio.create_task(replayer.run(tmp_queue), name="udp-replayer")
            try:
                while True:
                    get_task = asyncio.create_task(tmp_queue.get())
                    done, _ = await asyncio.wait({get_task, replay_task}, return_when=asyncio.FIRST_COMPLETED)

                    if replay_task in done:
                        get_task.cancel()
                        break

                    data = get_task.result()
                    stats.replay_sent += 1

                    if cfg.record_enabled:
                        recorder.try_enqueue(data)

                    await dispatch_queue.put(data)
            finally:
                reporter.stop()
                dispatcher.stop()
                recorder.stop()
                replayer.stop()

        tasks.append(asyncio.create_task(_replay_fanout(), name="replay-fanout"))

    else:
        log.info("Mode=UDP listen=%s:%s record=%s", cfg.udp_host, cfg.udp_port, cfg.record_enabled)
        listener = UdpListener(cfg.udp_host, cfg.udp_port, raw_queue, drop_when_full=True, stats=stats)
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
        reporter.stop()
        dispatcher.stop()
        recorder.stop()
        if listener:
            listener.stop()
        if replayer:
            replayer.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _engine_loop(state_mgr, engine, interval_s: float) -> None:
    import asyncio

    interval = max(0.2, float(interval_s))
    while True:
        await asyncio.sleep(interval)
        # leer estado de forma tolerante
        st = getattr(state_mgr, "state", None)
        if st is None and hasattr(state_mgr, "get_state"):
            st = state_mgr.get_state()
        if st is None:
            continue
        t = getattr(st, "latest_session_time", -1.0)
        engine.tick(st, float(t))
