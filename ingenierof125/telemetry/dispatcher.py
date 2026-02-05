from __future__ import annotations

import asyncio
import logging

from ingenierof125.telemetry.protocol import PacketHeader


class PacketDispatcher:
    def __init__(self, expected_packet_format: int, expected_game_year: int) -> None:
        self._log = logging.getLogger("ingenierof125.dispatcher")
        self._stop = asyncio.Event()
        self._expected_packet_format = expected_packet_format
        self._expected_game_year = expected_game_year

        self.received = 0
        self.dropped_bad_header = 0
        self.dropped_format_mismatch = 0

    def stop(self) -> None:
        self._stop.set()

    async def run(self, in_queue: "asyncio.Queue[bytes]") -> None:
        self._log.info("Dispatcher running")
        while not self._stop.is_set():
            try:
                data = await asyncio.wait_for(in_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            self.received += 1

            hdr = PacketHeader.try_parse(data)
            if hdr is None:
                self.dropped_bad_header += 1
                continue

            if hdr.packet_format != self._expected_packet_format or hdr.game_year != self._expected_game_year:
                self.dropped_format_mismatch += 1
                continue

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
