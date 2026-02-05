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
