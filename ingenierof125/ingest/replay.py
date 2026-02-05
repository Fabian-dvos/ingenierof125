from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import BinaryIO, Optional


MAGIC = b\"INGREC1\\0\"
_HEADER = struct.Struct(\"<8sH\")
_RECORD = struct.Struct(\"<QI\")


@dataclass(slots=True)
class ReplayStats:
    sent: int = 0


class PacketReplayer:
    def __init__(self, path: str, speed: float = 1.0, no_sleep: bool = False) -> None:
        self._path = path
        self._speed = max(0.01, float(speed))
        self._no_sleep = bool(no_sleep)
        self._log = logging.getLogger(\"ingenierof125.replay\")
        self._stop = asyncio.Event()
        self.stats = ReplayStats()

    def stop(self) -> None:
        self._stop.set()

    def _open(self) -> BinaryIO:
        f = open(self._path, \"rb\")
        magic, ver = _HEADER.unpack(f.read(_HEADER.size))
        if magic != MAGIC:
            raise ValueError(\"Replay: magic inválido (no es archivo ingrec)\")
        if ver != 1:
            raise ValueError(f\"Replay: versión no soportada: {ver}\")
        return f

    async def run(self, out_queue: \"asyncio.Queue[bytes]\") -> None:
        self._log.info(\"Replaying %s (speed=%.2f no_sleep=%s)\", self._path, self._speed, self._no_sleep)

        f: Optional[BinaryIO] = None
        try:
            f = self._open()
            first_ts: int | None = None
            last_ts: int | None = None

            while not self._stop.is_set():
                hdr = f.read(_RECORD.size)
                if not hdr or len(hdr) < _RECORD.size:
                    break

                ts_ns, length = _RECORD.unpack(hdr)
                payload = f.read(length)
                if len(payload) != length:
                    break

                if first_ts is None:
                    first_ts = ts_ns
                    last_ts = ts_ns

                if not self._no_sleep and last_ts is not None:
                    dt_ns = ts_ns - last_ts
                    if dt_ns > 0:
                        await asyncio.sleep((dt_ns / 1e9) / self._speed)
                last_ts = ts_ns

                await out_queue.put(payload)
                self.stats.sent += 1
        finally:
            if f:
                f.close()
            self._log.info(\"Replay finished: sent=%s\", self.stats.sent)
