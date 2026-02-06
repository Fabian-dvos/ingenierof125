from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import Optional, Tuple

MAGIC = b"INGREC1\0"
ING_HEADER = struct.Struct("<8sH")
ING_REC = struct.Struct("<QI")

PKT_HDR = struct.Struct("<HBBBBBQfIIBB")
PKT_HDR_SIZE = PKT_HDR.size  # 29

# F1 25 CarDamageData car struct: 46 bytes
CAR_DAMAGE_CAR = struct.Struct("<4f4B4B4B18B")
CAR_SZ = CAR_DAMAGE_CAR.size
NUM_CARS = 22

def parse_hdr(payload: bytes) -> Optional[Tuple]:
    if len(payload) < PKT_HDR_SIZE:
        return None
    return PKT_HDR.unpack_from(payload, 0)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=str)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"ERROR: not found: {p}")
        return 2

    max_fl = 0
    max_fr = 0
    seen = 0
    printed = 0

    with p.open("rb") as f:
        h = f.read(ING_HEADER.size)
        if len(h) != ING_HEADER.size:
            print("ERROR: header short")
            return 2
        magic, ver = ING_HEADER.unpack(h)
        if magic != MAGIC or ver != 1:
            print(f"ERROR: not ingrec v1 (magic={magic!r} ver={ver})")
            return 2

        while True:
            rec = f.read(ING_REC.size)
            if not rec or len(rec) < ING_REC.size:
                break
            ts_ns, length = ING_REC.unpack(rec)
            payload = f.read(length)
            if len(payload) != length:
                break

            hdr = parse_hdr(payload)
            if hdr is None:
                continue

            (
                packet_format, game_year, game_major, game_minor,
                packet_version, packet_id, session_uid, session_time,
                frame_identifier, overall_frame_identifier,
                player_car_index, secondary_player_car_index
            ) = hdr

            if int(packet_id) != 10:
                continue

            base = PKT_HDR_SIZE
            need = base + (NUM_CARS * CAR_SZ)
            if len(payload) < need:
                continue

            idx = int(player_car_index)
            off = base + idx * CAR_SZ
            car = CAR_DAMAGE_CAR.unpack_from(payload, off)

            fl = int(car[16])  # FL wing damage
            fr = int(car[17])  # FR wing damage

            seen += 1
            max_fl = max(max_fl, fl)
            max_fr = max(max_fr, fr)

            if (fl or fr) and printed < 15:
                printed += 1
                print(f"t={session_time:8.3f}s frame={frame_identifier} player={idx} FL={fl}% FR={fr}%")

            if args.limit and seen >= args.limit:
                break

    print(f"\nSUMMARY: packet10={seen} | max FL={max_fl}% max FR={max_fr}%")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
