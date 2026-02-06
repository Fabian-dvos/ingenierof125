from __future__ import annotations

from dataclasses import dataclass

from ingenierof125.engine.events import Event, Priority
from ingenierof125.rules.model import RuleConfig


def _get(obj, *names, default=None):
    if obj is None:
        return default
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default


@dataclass(slots=True)
class EventDetector:
    cfg: RuleConfig

    def detect(self, state) -> list[Event]:
        events: list[Event] = []

        # ---- Fuel ----
        status = _get(state, "status", default=None)
        status_v = _get(status, "value", default=None)

        rem_laps = _get(status_v, "fuel_remaining_laps", "rem_laps", "remaining_fuel_laps", default=None)
        fuel_kg = _get(status_v, "fuel_in_tank", "fuel", "fuel_kg", default=None)

        if rem_laps is not None:
            crit = self.cfg.threshold("fuel_rem_laps_critical", 1.0)
            low = self.cfg.threshold("fuel_rem_laps_low", 2.0)
            cd = self.cfg.cooldown("fuel_low", 25.0)

            if float(rem_laps) <= crit:
                events.append(Event(
                    key="fuel_low",
                    priority=Priority.IMMEDIATE_RISK,
                    urgency=1,
                    score=95.0,
                    cooldown_s=cd,
                    text=f"Combustible crítico: {float(rem_laps):.2f} vueltas",
                    data={"rem_laps": float(rem_laps), "fuel": fuel_kg},
                ))
            elif float(rem_laps) <= low:
                events.append(Event(
                    key="fuel_low",
                    priority=Priority.MANAGEMENT,
                    urgency=0,
                    score=60.0,
                    cooldown_s=cd,
                    text=f"Combustible justo: {float(rem_laps):.2f} vueltas",
                    data={"rem_laps": float(rem_laps), "fuel": fuel_kg},
                ))

        # ---- Penalty ----
        pen = _get(status_v, "penalty_seconds", "pen_seconds", "penalty_s", default=0.0)
        try:
            pen_f = float(pen or 0.0)
        except Exception:
            pen_f = 0.0

        if pen_f > 0.0:
            cd = self.cfg.cooldown("penalty", 10.0)
            events.append(Event(
                key="penalty",
                priority=Priority.IMMEDIATE_RISK,
                urgency=1,
                score=99.0,
                cooldown_s=cd,
                text=f"Penalización activa: {pen_f:.0f}s",
                data={"penalty_seconds": pen_f},
            ))

        # ---- Wing damage ----
        dmg = _get(state, "damage", default=None)
        dmg_v = _get(dmg, "value", default=None)
        fl = _get(dmg_v, "front_left_wing", "wing_l", "wingL", default=0)
        fr = _get(dmg_v, "front_right_wing", "wing_r", "wingR", default=0)

        try:
            fl_i = int(fl or 0)
            fr_i = int(fr or 0)
        except Exception:
            fl_i, fr_i = 0, 0

        max_w = max(fl_i, fr_i)
        if max_w > 0:
            warn = int(self.cfg.threshold("wing_damage_warn", 25))
            crit = int(self.cfg.threshold("wing_damage_critical", 60))
            cd = self.cfg.cooldown("wing_damage", 30.0)

            if max_w >= crit:
                events.append(Event(
                    key="wing_damage",
                    priority=Priority.IMMEDIATE_RISK,
                    urgency=1,
                    score=98.0,
                    cooldown_s=cd,
                    text=f"Alerón delantero muy dañado: {max_w}%",
                    data={"wingL": fl_i, "wingR": fr_i},
                ))
            elif max_w >= warn:
                events.append(Event(
                    key="wing_damage",
                    priority=Priority.IMMEDIATE_RISK,
                    urgency=0,
                    score=75.0,
                    cooldown_s=cd,
                    text=f"Alerón delantero dañado: {max_w}%",
                    data={"wingL": fl_i, "wingR": fr_i},
                ))

        return events
