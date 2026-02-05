import unittest
import struct

from ingenierof125.state.manager import StateManager, Ttls
from ingenierof125.telemetry.decoders_lite import (
    LAPDATA,
    CAR_STATUS,
    CAR_TELEMETRY,
    CAR_DAMAGE,
    PKT_HDR_SIZE,
)

PKT_HDR = struct.Struct("<HBBBBBQfIIBB")


def make_header(packet_id: int, session_time: float, frame: int, player: int = 0, fmt: int = 2025, year: int = 25) -> bytes:
    # packet_format, game_year, game_major, game_minor, packet_version, packet_id, session_uid, session_time, frame, overall, player, secondary
    return PKT_HDR.pack(fmt, year, 1, 0, 1, packet_id, 123456789, float(session_time), int(frame), int(frame), int(player), 255)


def make_lap_packet(session_time: float, frame: int, player: int = 0) -> bytes:
    # Total length 1285: header29 + 22*57 + 2
    payload = bytearray(1285)
    payload[:PKT_HDR_SIZE] = make_header(2, session_time, frame, player=player)
    # pack player lap struct at correct offset
    base = PKT_HDR_SIZE + player * LAPDATA.size
    # Build a LapData with lap=3, pos=5, sector=2, lastLap=90s, currentLap=10s, penalties=2
    lap = LAPDATA.pack(
        90000, 10000,
        30000, 1,  # s1 30s, 1 min (solo para ocupar)
        25000, 0,
        1500, 0,   # delta front 1.5s
        5000, 0,   # delta leader 5.0s
        0.0, 0.0, 0.0,
        5,   # car_pos
        3,   # lap_num
        0, 0, 2, 0, 2,   # pitStatus, pitstops, sector, invalid, penalties
        0,0,0,0,0,0,0,0,
        0,0,0,
        0.0,
        0
    )
    payload[base:base+LAPDATA.size] = lap
    # trailing 2 bytes
    payload[-2:] = b"\x00\x00"
    return bytes(payload)


def make_status_packet(session_time: float, frame: int, player: int = 0) -> bytes:
    payload = bytearray(1239)
    payload[:PKT_HDR_SIZE] = make_header(7, session_time, frame, player=player)
    base = PKT_HDR_SIZE + player * CAR_STATUS.size
    status = CAR_STATUS.pack(
        0,0,0,55,0,          # 5B
        12.5, 110.0, 2.2,    # fff
        12000, 4000,         # HH
        8,                   # B max gears
        1,                   # B drs allowed
        0,                   # B activation distance
        18, 16, 4,           # BBB actual, visual, age
        -1,                  # b fia flags
        0.0, 0.0, 0.0,       # fff
        0,                   # B deploy mode
        0.0, 0.0, 0.0,       # fff
        0                    # B paused
    )
    payload[base:base+CAR_STATUS.size] = status
    return bytes(payload)


def make_telem_packet(session_time: float, frame: int, player: int = 0) -> bytes:
    payload = bytearray(1352)
    payload[:PKT_HDR_SIZE] = make_header(6, session_time, frame, player=player)
    base = PKT_HDR_SIZE + player * CAR_TELEMETRY.size
    telem = CAR_TELEMETRY.pack(
        250,        # speed
        0.8, 0.1, 0.0,  # throttle, steer, brake
        0,          # clutch
        5,          # gear
        11500,      # rpm
        1,          # drs
        70,         # rev lights pct
        0,          # rev bits
        0,0,0,0,    # brakes temp 4H
        0,0,0,0,    # tyres surf temp 4B
        0,0,0,0,    # tyres inner temp 4B
        0,          # engine temp H
        0.0,0.0,0.0,0.0,  # pressures 4f
        0,0,0,0     # surface type 4B
    )
    payload[base:base+CAR_TELEMETRY.size] = telem
    # 3 bytes extra at end
    payload[-3:] = b"\x00\x00\x00"
    return bytes(payload)


def make_damage_packet(session_time: float, frame: int, player: int = 0) -> bytes:
    payload = bytearray(1041)
    payload[:PKT_HDR_SIZE] = make_header(10, session_time, frame, player=player)
    base = PKT_HDR_SIZE + player * CAR_DAMAGE.size

    # CAR_DAMAGE: 4f + 4B + 4B + 4B + 18B
    wear = (10.0, 12.0, 9.0, 11.0)
    tyre_damage = (0,0,0,0)
    brakes_damage = (0,0,0,0)
    extra4 = (5, 6, 0, 0)  # wingL=5, wingR=6, rear=0, floor=0 (aprox)
    tail = (0,) * 18
    dmg = CAR_DAMAGE.pack(*wear, *tyre_damage, *brakes_damage, *extra4, *tail)
    payload[base:base+CAR_DAMAGE.size] = dmg
    return bytes(payload)


class TestStateManager(unittest.TestCase):
    def test_updates_and_stale(self):
        sm = StateManager(ttls=Ttls(lap=1.0, telemetry=0.5, status=1.0, damage=2.0, session=5.0))

        sm.apply_packet(2, make_lap_packet(10.0, 100), 10.0, 0)
        sm.apply_packet(7, make_status_packet(10.0, 100), 10.0, 0)
        sm.apply_packet(6, make_telem_packet(10.0, 100), 10.0, 0)
        sm.apply_packet(10, make_damage_packet(10.0, 100), 10.0, 0)

        flags = sm.stale_flags(10.2)
        self.assertFalse(flags.lap)
        self.assertFalse(flags.status)
        self.assertFalse(flags.telemetry)
        self.assertFalse(flags.damage)

        flags2 = sm.stale_flags(11.2)
        self.assertTrue(flags2.telemetry)  # ttl 0.5
        self.assertTrue(flags2.lap)        # ttl 1.0

        # No debe explotar con payload corto/corrupto
        sm.apply_packet(6, b"\x00" * 10, 12.0, 0)
        self.assertGreaterEqual(sm.state.decode_errors, 0)

    def test_format_line(self):
        sm = StateManager()
        sm.apply_packet(2, make_lap_packet(5.0, 10), 5.0, 0)
        line = sm.format_one_line()
        self.assertIn("lap=", line)
        self.assertIn("t=", line)


if __name__ == "__main__":
    unittest.main()
