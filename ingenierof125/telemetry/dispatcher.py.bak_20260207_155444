from __future__ import annotations

import asyncio
import logging
from typing import Any

from ingenierof125.telemetry.protocol import PacketHeader
from ingenierof125.state.manager import StateManager


log = logging.getLogger("ingenierof125.dispatcher")


def _inc(stats: Any, *names: str, delta: int = 1) -> None:
    """Incrementa el primer campo existente en stats (compat multi-version)."""
    if stats is None:
        return
    for n in names:
        try:
            cur = getattr(stats, n)
        except Exception:
            continue
        try:
            setattr(stats, n, int(cur) + int(delta))
            return
        except Exception:
            pass
    # si ninguno existe, no hacemos nada (no queremos crashear)


def _get_dict(stats: Any, *names: str) -> dict | None:
    if stats is None:
        return None
    for n in names:
        try:
            d = getattr(stats, n)
        except Exception:
            continue
        if isinstance(d, dict):
            return d
    return None


def _set_if_exists(stats: Any, name: str, value: Any) -> None:
    if stats is None:
        return
    try:
        getattr(stats, name)
    except Exception:
        return
    try:
        setattr(stats, name, value)
    except Exception:
        return


class PacketDispatcher:
    def __init__(
        self,
        expected_packet_format: int,
        expected_game_year: int,
        stats: Any = None,
        state_manager: StateManager | None = None,
        *,
        strict_format: bool = False,
        strict_game_year: bool = False,
    ) -> None:
        self._stop = asyncio.Event()

        self._expected_packet_format = int(expected_packet_format)
        self._expected_game_year = int(expected_game_year)

        self._strict_format = bool(strict_format)
        self._strict_game_year = bool(strict_game_year)

        self._warned_format = False
        self._warned_year = False

        self._stats = stats
        self._state = state_manager

    def stop(self) -> None:
        self._stop.set()

    async def run(self, in_queue: "asyncio.Queue[bytes]") -> None:
        log.info("Dispatcher running")
        while not self._stop.is_set():
            try:
                data = await asyncio.wait_for(in_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            _inc(self._stats, "dispatched_in")

            hdr = PacketHeader.try_parse(data)
            if hdr is None:
                _inc(self._stats, "dropped_bad_header", "drop_bad_hdr")
                continue

            # checks packet_format
            if int(hdr.packet_format) != self._expected_packet_format:
                if self._strict_format:
                    _inc(self._stats, "dropped_format", "dropped_format_mismatch", "drop_fmt")
                    continue
                if not self._warned_format:
                    self._warned_format = True
                    log.warning(
                        "packet_format mismatch (got=%s expected=%s) strict_format=False -> ACCEPTING",
                        hdr.packet_format,
                        self._expected_packet_format,
                    )

            # checks game_year
            if int(hdr.game_year) != self._expected_game_year:
                if self._strict_game_year:
                    _inc(self._stats, "dropped_game_year", "dropped_game_year_mismatch", "drop_year")
                    continue
                if not self._warned_year:
                    self._warned_year = True
                    log.warning(
                        "game_year mismatch (got=%s expected=%s) strict_game_year=False -> ACCEPTING",
                        hdr.game_year,
                        self._expected_game_year,
                    )

            # ids counter (compat: ids o by_packet_id)
            d = _get_dict(self._stats, "ids", "by_packet_id")
            if d is not None:
                pid = int(hdr.packet_id)
                d[pid] = int(d.get(pid, 0)) + 1

            # opcionales (si existen en stats)
            _set_if_exists(self._stats, "last_packet_id", int(hdr.packet_id))
            _set_if_exists(self._stats, "last_frame", int(hdr.frame_identifier))
            _set_if_exists(self._stats, "last_session_uid", int(hdr.session_uid))

            # state update
            if self._state is not None:
                try:
                    self._state.apply_packet(
                        packet_id=int(hdr.packet_id),
                        payload=data,
                        session_time=float(hdr.session_time),
                        player_index=int(hdr.player_car_index),
                    )
                except Exception:
                    _inc(self._stats, "decode_errors", "dec_errors")
                    if log.isEnabledFor(logging.DEBUG):
                        log.exception("apply_packet failed")