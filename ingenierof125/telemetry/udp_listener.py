from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass


@dataclass(slots=True)
class _UdpProtocol(asyncio.DatagramProtocol):
    out_queue: "asyncio.Queue[bytes]"
    drop_when_full: bool
    log: logging.Logger
    dropped: int = 0

    def datagram_received(self, data: bytes, addr) -> None:  # type: ignore[override]
        if self.drop_when_full and self.out_queue.full():
            self.dropped += 1
            return
        try:
            self.out_queue.put_nowait(data)
        except asyncio.QueueFull:
            self.dropped += 1


class UdpListener:
    def __init__(self, host: str, port: int, out_queue: "asyncio.Queue[bytes]", drop_when_full: bool = True) -> None:
        self._host = host
        self._port = port
        self._out_queue = out_queue
        self._drop_when_full = drop_when_full
        self._log = logging.getLogger("ingenierof125.udp")
        self._stop = asyncio.Event()
        self._transport: asyncio.DatagramTransport | None = None

    def stop(self) -> None:
        self._stop.set()
        if self._transport is not None:
            self._transport.close()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        protocol = _UdpProtocol(self._out_queue, self._drop_when_full, self._log)
        transport, _ = await loop.create_datagram_endpoint(lambda: protocol, local_addr=(self._host, self._port))
        self._transport = transport  # type: ignore[assignment]
        self._log.info("Listening UDP on %s:%s", self._host, self._port)

        try:
            while not self._stop.is_set():
                await asyncio.sleep(1.0)
        finally:
            self.stop()
