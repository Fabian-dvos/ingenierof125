from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


MAGIC = b"INGREC1\0"  # 8 bytes
VERSION = 1
_HEADER = struct.Struct("<8sH")        # magic + u16 version
_RECORD = struct.Struct("<QI")         # u64 ts_ns + u32 length


@dataclass(slots=True)
class RecorderStats:
    written: int = 0
    dropped: int = 0


class PacketRecorder:
    def __init__(
        self,
        out_dir: str = "recordings",
        enabled: bool = False,
        queue_maxsize: int = 4096,
        flush_every: int = 64,
    ) -> None:
        self._enabled = enabled
        self._out_dir = out_dir
        self._flush_every = max(1, int(flush_every))
        self._log = logging.getLogger("ingenierof125.recorder")
        self._stop = asyncio.Event()
        self.stats = RecorderStats()

        self._queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue(maxsize=queue_maxsize)
        self._file = None  # type: Optional[object]
        self._path: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> str | None:
        return self._path

    def stop(self) -> None:
        self._stop.set()

    def try_enqueue(self, payload: bytes, ts_ns: int | None = None) -> None:
        if not self._enabled:
            return
        if ts_ns is None:
            ts_ns = time.time_ns()
        try:
            self._queue.put_nowait((ts_ns, payload))
        except asyncio.QueueFull:
            self.stats.dropped += 1

    def _open(self) -> None:
        os.makedirs(self._out_dir, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_f1udp.ingrec"
        self._path = os.path.join(self._out_dir, name)
        f = open(self._path, "wb", buffering=1024 * 1024)
        f.write(_HEADER.pack(MAGIC, VERSION))
        self._file = f
        self._log.info("Recording to %s", self._path)

    def _close(self) -> None:
        try:
            if self._file:
                self._file.flush()
                self._file.close()
        finally:
            self._file = None

    async def run(self) -> None:
        if not self._enabled:
            return

        self._open()
        assert self._file is not None

        buffered = 0
        try:
            while not self._stop.is_set():
                try:
                    ts_ns, payload = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if len(payload) > 0xFFFFFFFF:
                    self.stats.dropped += 1
                    continue

                self._file.write(_RECORD.pack(ts_ns, len(payload)))
                self._file.write(payload)
                self.stats.written += 1
                buffered += 1

                if buffered >= self._flush_every:
                    self._file.flush()
                    buffered = 0
        finally:
            self._close()
