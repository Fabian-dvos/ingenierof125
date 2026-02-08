from __future__ import annotations

import asyncio
import logging

from ingenierof125.core.stats import RuntimeStats
from ingenierof125.state.manager import StateManager
from ingenierof125.telemetry.protocol import PacketHeader


class PacketDispatcher:
    def __init__(
        self,
        expected_packet_format: int,
        expected_game_year: int,
        stats: RuntimeStats | None = None,
        state_manager: StateManager | None = None,
        *,
        strict_format: bool = False,
        strict_game_year: bool = False,
    ) -> None:
        self._log = logging.getLogger("ingenierof125.dispatcher")
        self._stop = asyncio.Event()

        self._expected_packet_format = int(expected_packet_format)
        self._expected_game_year = int(expected_game_year)

        self._strict_format = bool(strict_format)
        self._strict_game_year = bool(strict_game_year)

        self._warned_format = False
        self._warned_year = False

        self._stats = stats or RuntimeStats()
        self._state = state_manager

    def stop(self) -> None:
        self._stop.set()

    def _touch_ids(self, packet_id: int) -> None:
        # RuntimeStats.ids hoy es list[int]. Si mañana pasa a dict, también banca.
        try:
            ids = self._stats.ids
        except Exception:
            return

        if isinstance(ids, list):
            if packet_id not in ids:
                ids.append(packet_id)
                # mantenemos un buffer chico (debug)
                if len(ids) > 24:
                    del ids[: len(ids) - 24]
        elif isinstance(ids, dict):
            ids[packet_id] = int(ids.get(packet_id, 0)) + 1

    async def run(self, in_queue: "asyncio.Queue[bytes]") -> None:
        self._log.info("Dispatcher running")
        while not self._stop.is_set():
            try:
                data = await asyncio.wait_for(in_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            self._stats.dispatched_in += 1

            hdr = PacketHeader.try_parse(data)
            if hdr is None:
                self._stats.drop_bad_hdr += 1
                continue

            if hdr.packet_format != self._expected_packet_format:
                if self._strict_format:
                    self._stats.drop_fmt += 1
                    continue
                if not self._warned_format:
                    self._warned_format = True
                    self._log.warning(
                        "packet_format mismatch (got=%s expected=%s) but strict_format=False -> ACCEPTING",
                        hdr.packet_format,
                        self._expected_packet_format,
                    )

            if hdr.game_year != self._expected_game_year:
                if self._strict_game_year:
                    self._stats.drop_year += 1
                    continue
                if not self._warned_year:
                    self._warned_year = True
                    self._log.warning(
                        "game_year mismatch (got=%s expected=%s) but strict_game_year=False -> ACCEPTING",
                        hdr.game_year,
                        self._expected_game_year,
                    )

            # debug ids
            self._touch_ids(int(hdr.packet_id))

            # Actualiza estado normalizado
            if self._state is not None:
                try:
                    self._state.apply_packet(
                        packet_id=int(hdr.packet_id),
                        payload=data,
                        session_time=float(hdr.session_time),
                        player_index=int(hdr.player_car_index),
                    )
                except Exception:
                    self._stats.dec_err += 1
                    if self._log.isEnabledFor(logging.DEBUG):
                        self._log.exception("apply_packet failed")