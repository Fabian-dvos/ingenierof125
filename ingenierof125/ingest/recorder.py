from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from ingenierof125.core.stats import RuntimeStats

log = logging.getLogger("ingenierof125.recorder")

MAGIC = b"INGREC1\0"              # 8 bytes
_HEADER = struct.Struct("<8sH")   # magic + u16 version
_RECORD = struct.Struct("<QI")    # u64 ts_ns + u32 length


@dataclass(slots=True)
class RecorderStats:
    enqueued: int = 0
    dropped: int = 0
    written: int = 0
    last_path: str = ""


class PacketRecorder:
    """
    Recorder compatible hacia atrás.

    Soporta:
      - queue_maxsize (nuevo)
      - max_queue (viejo alias)
      - stats=RuntimeStats (viejo) opcional
    """

    def __init__(
        self,
        out_dir: str = "recordings",
        enabled: bool = False,
        queue_maxsize: int = 2048,
        flush_every: int = 64,
        *,
        max_queue: Optional[int] = None,          # alias viejo
        stats: Optional[RuntimeStats] = None,     # opcional viejo
        **_ignored: Any,                          # traga kwargs desconocidos
    ) -> None:
        if max_queue is not None:
            try:
                queue_maxsize = int(max_queue)
            except Exception:
                pass

        self._out_dir = out_dir
        self._enabled = bool(enabled)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=int(queue_maxsize))
        self._flush_every = max(1, int(flush_every))
        self._stop = asyncio.Event()

        self.stats = RecorderStats()
        self._rstats = stats  # RuntimeStats opcional

    def stop(self) -> None:
        self._stop.set()

    def try_enqueue(self, payload: bytes) -> bool:
        if not self._enabled:
            return False
        try:
            self._queue.put_nowait(payload)
            self.stats.enqueued += 1
            return True
        except asyncio.QueueFull:
            self.stats.dropped += 1
            if self._rstats is not None:
                self._rstats.rec_drop += 1
            return False

    async def enqueue(self, payload: bytes) -> bool:
        # Compat: algunos callers usan "await recorder.enqueue(...)"
        return self.try_enqueue(payload)

    def _new_path(self) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        Path(self._out_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(self._out_dir) / f"{ts}_f1udp.ingrec")

    async def run(self, stop_evt: Optional[asyncio.Event] = None) -> None:
        if not self._enabled:
            # Igual esperamos stop para no romper pipeline
            while True:
                if self._stop.is_set() or (stop_evt is not None and stop_evt.is_set()):
                    return
                await asyncio.sleep(0.2)

        path = self._new_path()
        self.stats.last_path = path
        log.info("Recording to %s", path)

        f = open(path, "wb")
        try:
            f.write(_HEADER.pack(MAGIC, 1))

            buf: list[tuple[int, bytes]] = []

            def flush() -> None:
                if not buf:
                    return
                for ts_ns, payload in buf:
                    f.write(_RECORD.pack(int(ts_ns), len(payload)))
                    f.write(payload)

                n = len(buf)
                self.stats.written += n
                if self._rstats is not None:
                    self._rstats.rec_written += n

                buf.clear()
                f.flush()

            while True:
                if self._stop.is_set() or (stop_evt is not None and stop_evt.is_set()):
                    flush()
                    return

                try:
                    payload = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    flush()
                    continue

                buf.append((time.time_ns(), payload))
                if len(buf) >= self._flush_every:
                    flush()

        finally:
            try:
                f.flush()
            except Exception:
                pass
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
            f.close()