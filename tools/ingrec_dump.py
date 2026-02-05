from __future__ import annotations

import argparse
import os
import struct
from collections import Counter
from pathlib import Path
from typing import Optional, Tuple


# Nuestro formato .ingrec
MAGIC = b"INGREC1\0"              # 8 bytes
ING_HEADER = struct.Struct("<8sH")  # magic + u16 ver
ING_REC = struct.Struct("<QI")      # u64 ts_ns + u32 length

# F1 UDP header (29 bytes) - lo que ya estás usando en el dispatcher
PKT_HDR = struct.Struct("<HBBBBBQfIIBB")
PKT_HDR_SIZE = PKT_HDR.size  # 29


def parse_f1_header(payload: bytes) -> Optional[Tuple[int, int, int, int, int, int, int, float, int, int, int, int]]:
    if len(payload) < PKT_HDR_SIZE:
        return None
    return PKT_HDR.unpack_from(payload, 0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect .ingrec recordings (header + counts + duration)")
    ap.add_argument("path", type=str, help="Path to .ingrec")
    ap.add_argument("--every", type=float, default=1.0, help="Print one line every N seconds of recording time")
    ap.add_argument("--max-seconds", type=float, default=0.0, help="Stop after N seconds (0=all)")
    ap.add_argument("--max-packets", type=int, default=0, help="Stop after N packets (0=all)")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"ERROR: file not found: {p}")
        return 2

    size = os.path.getsize(p)
    counts = Counter()
    lens = Counter()

    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    last_print_t: float = -1e9

    last_frame: Optional[int] = None
    last_packet_id: Optional[int] = None
    last_session_uid: Optional[int] = None
    last_session_time: Optional[float] = None

    bad_headers = 0
    total = 0

    with p.open("rb") as f:
        h = f.read(ING_HEADER.size)
        if len(h) != ING_HEADER.size:
            print("ERROR: ingrec header too short")
            return 2
        magic, ver = ING_HEADER.unpack(h)
        if magic != MAGIC or ver != 1:
            print(f"ERROR: not an ingrec v1 (magic={magic!r} ver={ver})")
            return 2

        while True:
            rec = f.read(ING_REC.size)
            if not rec or len(rec) < ING_REC.size:
                break

            ts_ns, length = ING_REC.unpack(rec)
            payload = f.read(length)
            if len(payload) != length:
                break

            total += 1
            if first_ts is None:
                first_ts = ts_ns
            last_ts = ts_ns

            if args.max_packets and total >= args.max_packets:
                break

            t = (ts_ns - first_ts) / 1e9 if first_ts else 0.0
            if args.max_seconds and t >= args.max_seconds:
                break

            lens[length] += 1

            fh = parse_f1_header(payload)
            if fh is None:
                bad_headers += 1
                continue

            (
                packet_format,
                game_year,
                game_major,
                game_minor,
                packet_version,
                packet_id,
                session_uid,
                session_time,
                frame_identifier,
                overall_frame_identifier,
                player_car_index,
                secondary_player_car_index,
            ) = fh

            counts[int(packet_id)] += 1
            last_frame = int(frame_identifier)
            last_packet_id = int(packet_id)
            last_session_uid = int(session_uid)
            last_session_time = float(session_time)

            if (t - last_print_t) >= float(args.every):
                last_print_t = t
                print(
                    f"t={t:8.3f}s frame={frame_identifier} id={packet_id} ver={packet_version} "
                    f"sess_uid={session_uid} sess_t={session_time:.3f} fmt={packet_format} year={game_year} "
                    f"player={player_car_index} len={length}"
                )

    dur = 0.0
    if first_ts is not None and last_ts is not None:
        dur = (last_ts - first_ts) / 1e9

    print("\n=== SUMMARY ===")
    print(f"file: {p}")
    print(f"filesize: {size} bytes")
    print(f"records: {total}")
    print(f"duration: {dur:.3f} s")
    print(f"bad_headers(<29B): {bad_headers}")
    if last_session_uid is not None:
        print(f"last: sess_uid={last_session_uid} sess_time={last_session_time:.3f} frame={last_frame} id={last_packet_id}")

    if counts:
        print("packet_id counts:")
        for k in sorted(counts.keys()):
            print(f"  {k:>2}: {counts[k]}")
    else:
        print("packet_id counts: (none parsed)")

    # top payload lengths
    print("top payload lengths:")
    for length, c in lens.most_common(10):
        print(f"  len={length}: {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
