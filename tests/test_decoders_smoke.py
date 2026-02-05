import unittest
import struct

from ingenierof125.telemetry.decoders_lite import decode_session, PKT_HDR_SIZE

PKT_HDR = struct.Struct("<HBBBBBQfIIBB")


def make_header(packet_id: int, session_time: float) -> bytes:
    return PKT_HDR.pack(2025, 25, 1, 0, 1, packet_id, 1, float(session_time), 1, 1, 0, 255)


class TestDecodersSmoke(unittest.TestCase):
    def test_session_min_fields(self):
        # payload 753 with some fields set
        payload = bytearray(753)
        payload[:PKT_HDR_SIZE] = make_header(1, 1.0)
        off = PKT_HDR_SIZE
        payload[off] = 1  # weather
        payload[off+1] = 30  # track temp (int8 but ok)
        payload[off+2] = 20  # air temp
        payload[off+3] = 5   # total laps
        # track length u16
        payload[off+4:off+6] = (5000).to_bytes(2, "little", signed=False)

        s = decode_session(bytes(payload))
        self.assertIsNotNone(s)
        assert s is not None
        self.assertEqual(s.weather, 1)
        self.assertEqual(s.total_laps, 5)


if __name__ == "__main__":
    unittest.main()
