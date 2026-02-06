import struct
import unittest

from ingenierof125.telemetry.decoders_lite import decode_damage_player

PKT_HDR = struct.Struct("<HBBBBBQfIIBB")     # 29 bytes
CAR = struct.Struct("<4f4B4B4B18B")          # 46 bytes
NUM_CARS = 22
PKT_HDR_SIZE = PKT_HDR.size

def build_damage_packet(player_idx: int, fl: int, fr: int, gb: int, eng: int) -> bytes:
    hdr = PKT_HDR.pack(2025, 25, 1, 0, 1, 10, 123, 1.0, 77, 77, player_idx, 255)

    base = [
        0.0, 0.0, 0.0, 0.0,          # wear
        0, 0, 0, 0,                  # tyresDamage
        0, 0, 0, 0,                  # brakesDamage
        0, 0, 0, 0,                  # blisters
        fl, fr, 0, 0, 0, 0,          # FL, FR, rearWing, floor, diffuser, sidepod
        0, 0,                        # drsFault, ersFault
        gb, eng,                     # gearbox, engine
        0, 0, 0, 0, 0, 0,            # engine wears
        0, 0                         # blown, seized
    ]
    car0 = CAR.pack(*base)
    cars = car0 + (b"\x00" * CAR.size) * (NUM_CARS - 1)
    return hdr + cars

class TestDamageOffsets(unittest.TestCase):
    def test_wing_offsets(self):
        pkt = build_damage_packet(0, 77, 88, 55, 66)
        out = decode_damage_player(pkt, 0)
        self.assertIsNotNone(out)
        self.assertEqual(int(out.front_left_wing), 77)
        self.assertEqual(int(out.front_right_wing), 88)
        self.assertEqual(int(out.gearbox_damage), 55)
        self.assertEqual(int(out.engine_damage), 66)

if __name__ == "__main__":
    unittest.main(verbosity=2)
