from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

# F1 UDP header size (ya usado en dispatcher/protocol)
PKT_HDR_SIZE = 29
N_CARS = 22

# Wheel order (documentado): 0 RL, 1 RR, 2 FL, 3 FR
WHEELS = ("RL", "RR", "FL", "FR")


def _finite(x: float) -> bool:
    return not (math.isnan(x) or math.isinf(x))


def _clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _ms_from_parts(ms_part: int, min_part: int) -> int:
    # minutes * 60_000 + ms
    return int(min_part) * 60_000 + int(ms_part)


# LapData (57 bytes) * 22 + 2 bytes extra => 1285 total con header
LAPDATA = struct.Struct("<IIHBHBHBHBfff15BHHBfB")

# CarTelemetryData (60 bytes) * 22 + 3 bytes extra => 1352 total con header
CAR_TELEMETRY = struct.Struct("<HfffBbHBBH4H4B4BH4f4B")

# CarStatusData (55 bytes) * 22 => 1239 total con header
CAR_STATUS = struct.Struct("<5BfffHHBBHBBBbfffBfffB")

# CarDamageData (46 bytes) * 22 => 1041 total con header
CAR_DAMAGE = struct.Struct("<4f4B4B4B18B")


@dataclass(slots=True)
class SessionLite:
    weather: int = 0
    track_temp_c: int = 0
    air_temp_c: int = 0
    total_laps: int = 0
    track_length_m: int = 0
    session_type: int = 0
    track_id: int = -1
    safety_car_status: int = 0
    rain_next_10m_pct: Optional[int] = None


@dataclass(slots=True)
class PlayerLapLite:
    lap_num: int = 0
    position: int = 0
    sector: int = 0
    last_lap_ms: int = 0
    current_lap_ms: int = 0
    delta_front_ms: int = 0
    delta_leader_ms: int = 0
    penalties_s: int = 0


@dataclass(slots=True)
class PlayerStatusLite:
    fuel_in_tank: float = 0.0
    fuel_remaining_laps: float = 0.0
    actual_compound: int = 0
    visual_compound: int = 0
    tyre_age_laps: int = 0
    drs_allowed: int = 0


@dataclass(slots=True)
class PlayerDamageLite:
    wear: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    front_left_wing: int = 0
    front_right_wing: int = 0
    gearbox_damage: int = 0
    engine_damage: int = 0


@dataclass(slots=True)
class PlayerTelemetryLite:
    speed_kph: int = 0
    throttle: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    gear: int = 0
    drs: int = 0
    engine_rpm: int = 0


def compound_name(actual: int, visual: int) -> str:
    # Nota: mapping parcial suficiente para UI/logs. Ajustamos después con reglas/config.
    actual_map = {
        0: "UNK",
        7: "INTER",
        8: "WET",
        16: "C5",
        17: "C4",
        18: "C3",
        19: "C2",
        20: "C1",
        21: "C0",
        22: "C6",
    }
    visual_map = {
        0: "UNK",
        7: "INTER",
        8: "WET",
        16: "SOFT",
        17: "MED",
        18: "HARD",
    }
    a = actual_map.get(int(actual), f"A{actual}")
    v = visual_map.get(int(visual), f"V{visual}")
    return f"{a}/{v}"


def decode_session(payload: bytes) -> Optional[SessionLite]:
    # PacketSessionData total típico: 753 bytes
    if len(payload) < 753:
        return None
    off = PKT_HDR_SIZE

    # Primer bloque estable
    weather = payload[off]
    off += 1
    track_temp = struct.unpack_from("<b", payload, off)[0]
    off += 1
    air_temp = struct.unpack_from("<b", payload, off)[0]
    off += 1
    total_laps = payload[off]
    off += 1
    track_len = struct.unpack_from("<H", payload, off)[0]
    off += 2
    session_type = payload[off]
    off += 1
    track_id = struct.unpack_from("<b", payload, off)[0]
    off += 1

    # formula
    off += 1
    # sessionTimeLeft, sessionDuration
    off += 2 + 2

    # pitSpeedLimit + gamePaused + isSpectating + spectatorCarIndex + sliProNativeSupport + numMarshalZones
    num_marshal_zones = payload[off + 5]
    off += 6

    # MarshalZone[21] (float + int8) => 5 bytes each
    off += 21 * 5

    safety_car_status = payload[off]
    off += 1

    # networkGame
    off += 1

    num_weather_samples = payload[off]
    off += 1

    # WeatherForecastSample[64] => 8 bytes each
    best_10m: Optional[int] = None
    for i in range(64):
        st = payload[off]
        time_offset_min = payload[off + 1]
        rain_pct = payload[off + 7]
        if i < int(num_weather_samples) and st == session_type and time_offset_min <= 10:
            rp = int(rain_pct)
            if best_10m is None or rp > best_10m:
                best_10m = rp
        off += 8

    return SessionLite(
        weather=int(weather),
        track_temp_c=int(track_temp),
        air_temp_c=int(air_temp),
        total_laps=int(total_laps),
        track_length_m=int(track_len),
        session_type=int(session_type),
        track_id=int(track_id),
        safety_car_status=int(safety_car_status),
        rain_next_10m_pct=best_10m,
    )


def decode_lap_player(payload: bytes, player_idx: int) -> Optional[PlayerLapLite]:
    if len(payload) < 1285:
        return None
    if not (0 <= player_idx < N_CARS):
        return None
    base = PKT_HDR_SIZE + player_idx * LAPDATA.size
    if base + LAPDATA.size > len(payload):
        return None

    (
        last_lap_ms,
        current_lap_ms,
        s1_ms,
        s1_min,
        s2_ms,
        s2_min,
        d_front_ms,
        d_front_min,
        d_lead_ms,
        d_lead_min,
        lap_distance,
        total_distance,
        safety_car_delta,
        car_pos,
        lap_num,
        pit_status,
        num_pit_stops,
        sector,
        lap_invalid,
        penalties,
        total_warnings,
        corner_cut_warnings,
        unserved_dt,
        unserved_sg,
        grid_pos,
        driver_status,
        result_status,
        pit_lane_timer_active,
        pit_lane_ms,
        pit_stop_ms,
        pit_should_serve_pen,
        speedtrap_fastest_speed,
        speedtrap_fastest_lap,
    ) = LAPDATA.unpack_from(payload, base)

    return PlayerLapLite(
        lap_num=int(lap_num),
        position=int(car_pos),
        sector=int(sector),
        last_lap_ms=int(last_lap_ms),
        current_lap_ms=int(current_lap_ms),
        delta_front_ms=_ms_from_parts(d_front_ms, d_front_min),
        delta_leader_ms=_ms_from_parts(d_lead_ms, d_lead_min),
        penalties_s=int(penalties),
    )


def decode_status_player(payload: bytes, player_idx: int) -> Optional[PlayerStatusLite]:
    if len(payload) < 1239:
        return None
    if not (0 <= player_idx < N_CARS):
        return None
    base = PKT_HDR_SIZE + player_idx * CAR_STATUS.size
    if base + CAR_STATUS.size > len(payload):
        return None

    (
        traction_control,
        abs_on,
        fuel_mix,
        front_brake_bias,
        pit_limiter,
        fuel_in_tank,
        fuel_capacity,
        fuel_remaining_laps,
        max_rpm,
        idle_rpm,
        max_gears,
        drs_allowed,
        drs_activation_distance,
        actual_compound,
        visual_compound,
        tyre_age_laps,
        fia_flags,
        engine_power_ice,
        engine_power_mguk,
        ers_store_energy,
        ers_deploy_mode,
        ers_harvest_mguk,
        ers_harvest_mguh,
        ers_deployed_lap,
        network_paused,
    ) = CAR_STATUS.unpack_from(payload, base)

    ft = float(fuel_in_tank)
    fr = float(fuel_remaining_laps)
    if not (_finite(ft) and _finite(fr)):
        return None

    return PlayerStatusLite(
        fuel_in_tank=max(0.0, ft),
        fuel_remaining_laps=fr,
        actual_compound=int(actual_compound),
        visual_compound=int(visual_compound),
        tyre_age_laps=int(tyre_age_laps),
        drs_allowed=int(drs_allowed),
    )


def decode_telemetry_player(payload: bytes, player_idx: int) -> Optional[PlayerTelemetryLite]:
    if len(payload) < 1352:
        return None
    if not (0 <= player_idx < N_CARS):
        return None
    base = PKT_HDR_SIZE + player_idx * CAR_TELEMETRY.size
    if base + CAR_TELEMETRY.size > len(payload):
        return None

    (
        speed_kph,
        throttle,
        steer,
        brake,
        clutch,
        gear,
        engine_rpm,
        drs,
        rev_pct,
        rev_bits,
        bt0,
        bt1,
        bt2,
        bt3,
        ts0,
        ts1,
        ts2,
        ts3,
        ti0,
        ti1,
        ti2,
        ti3,
        engine_temp,
        p0,
        p1,
        p2,
        p3,
        st0,
        st1,
        st2,
        st3,
    ) = CAR_TELEMETRY.unpack_from(payload, base)

    thr = float(throttle)
    brk = float(brake)
    strv = float(steer)
    if not (_finite(thr) and _finite(brk) and _finite(strv)):
        return None

    return PlayerTelemetryLite(
        speed_kph=int(speed_kph),
        throttle=_clamp(thr, 0.0, 1.0),
        brake=_clamp(brk, 0.0, 1.0),
        steer=_clamp(strv, -1.0, 1.0),
        gear=int(gear),
        drs=int(drs),
        engine_rpm=int(engine_rpm),
    )


def decode_damage_player(payload: bytes, player_idx: int) -> Optional[PlayerDamageLite]:
    if len(payload) < 1041:
        return None
    if not (0 <= player_idx < N_CARS):
        return None
    base = PKT_HDR_SIZE + player_idx * CAR_DAMAGE.size
    if base + CAR_DAMAGE.size > len(payload):
        return None

    unpacked = CAR_DAMAGE.unpack_from(payload, base)
    wear = tuple(float(_clamp(x, 0.0, 100.0)) for x in unpacked[0:4])  # type: ignore[misc]

    # offsets:
    # 0..3 floats (16B)
    # 4 tyreDamage[4] (4B) => idx 4..7
    # 8 brakesDamage[4] (4B) => idx 8..11
    # then: frontLeftWing(1), frontRightWing(1), rearWing(1), floor(1), diffuser(1), sidepod(1),
    # drsFault(1), ersFault(1), gearbox(1), engine(1), +18 bytes
    front_left_wing = int(unpacked[12])
    front_right_wing = int(unpacked[13])
    gearbox_damage = int(unpacked[20])
    engine_damage = int(unpacked[21])

    return PlayerDamageLite(
        wear=(wear[0], wear[1], wear[2], wear[3]),
        front_left_wing=front_left_wing,
        front_right_wing=front_right_wing,
        gearbox_damage=gearbox_damage,
        engine_damage=engine_damage,
    )
