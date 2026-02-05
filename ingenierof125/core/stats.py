from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class RuntimeStats:
    # UDP layer
    udp_received: int = 0
    udp_dropped_queue: int = 0

    # Replay layer
    replay_sent: int = 0

    # Dispatcher layer
    dispatched_in: int = 0
    dropped_bad_header: int = 0
    dropped_format_mismatch: int = 0
    by_packet_id: dict[int, int] = field(default_factory=dict)

    # Last seen (debug)
    last_session_uid: int | None = None
    last_frame: int | None = None
    last_packet_id: int | None = None


class StatsReporter:
    def __init__(
        self,
        stats: RuntimeStats,
        interval_s: float = 2.0,
        raw_queue: Optional["asyncio.Queue[bytes]"] = None,
        dispatch_queue: Optional["asyncio.Queue[bytes]"] = None,
        recorder: object | None = None,
    ) -> None:
        self._stats = stats
        self._interval_s = max(0.5, float(interval_s))
        self._raw_queue = raw_queue
        self._dispatch_queue = dispatch_queue
        self._recorder = recorder

        self._stop = asyncio.Event()
        self._log = logging.getLogger("ingenierof125.stats")

        self._last_ts = time.monotonic()
        self._last_udp = 0
        self._last_replay = 0

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self._interval_s)

            now = time.monotonic()
            dt = max(1e-6, now - self._last_ts)

            udp_delta = self._stats.udp_received - self._last_udp
            udp_pps = udp_delta / dt

            replay_delta = self._stats.replay_sent - self._last_replay
            replay_pps = replay_delta / dt

            raw_q = None if self._raw_queue is None else f"{self._raw_queue.qsize()}/{self._raw_queue.maxsize}"
            dis_q = None if self._dispatch_queue is None else f"{self._dispatch_queue.qsize()}/{self._dispatch_queue.maxsize}"

            rec_written = None
            rec_dropped = None
            try:
                if self._recorder is not None and hasattr(self._recorder, "stats"):
                    s = getattr(self._recorder, "stats")
                    rec_written = getattr(s, "written", None)
                    rec_dropped = getattr(s, "dropped", None)
            except Exception:
                pass

            ids = dict(sorted(self._stats.by_packet_id.items()))
            last = f"sess={self._stats.last_session_uid} frame={self._stats.last_frame} id={self._stats.last_packet_id}"

            extra = []
            if raw_q is not None:
                extra.append(f"raw_q={raw_q}")
            if dis_q is not None:
                extra.append(f"dispatch_q={dis_q}")
            if rec_written is not None:
                extra.append(f"rec_written={rec_written}")
            if rec_dropped is not None:
                extra.append(f"rec_drop={rec_dropped}")

            self._log.info(
                "udp_rx=%s (%.1f/s) udp_dropQ=%s | replay_sent=%s (%.1f/s) | ok_in=%s bad_hdr=%s bad_fmt=%s | %s | ids=%s | %s",
                self._stats.udp_received,
                udp_pps,
                self._stats.udp_dropped_queue,
                self._stats.replay_sent,
                replay_pps,
                self._stats.dispatched_in,
                self._stats.dropped_bad_header,
                self._stats.dropped_format_mismatch,
                " ".join(extra),
                ids,
                last,
            )

            self._last_ts = now
            self._last_udp = self._stats.udp_received
            self._last_replay = self._stats.replay_sent
