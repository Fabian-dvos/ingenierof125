from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PacketHeader:
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int

    # F1 25 header: 29 bytes, little-endian, packed
    _STRUCT = struct.Struct("<HBBBBBQfIIBB")

    @staticmethod
    def try_parse(data: bytes) -> "PacketHeader | None":
        if len(data) < PacketHeader._STRUCT.size:
            return None
        try:
            pf, gy, gmaj, gmin, pver, pid, suid, st, frame, oframe, pci, spci = PacketHeader._STRUCT.unpack_from(data, 0)
            return PacketHeader(pf, gy, gmaj, gmin, pver, pid, suid, st, frame, oframe, pci, spci)
        except Exception:
            return None
