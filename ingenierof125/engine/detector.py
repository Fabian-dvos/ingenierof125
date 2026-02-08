from __future__ import annotations

from dataclasses import dataclass

from ingenierof125.engine.events import Event, Priority
from ingenierof125.rules.model import RuleConfig


@dataclass(slots=True)
class EventDetector:
    cfg: RuleConfig

    # safety_car_status tracking (Session packet)
    _last_sc_status: int = 0          # raw code (0,1,2,3,4,...)
    _last_active_sc: int = 0          # last "real" SC type: 1=SC, 2=VSC

    def detect(self, st) -> list[Event]:
        events: list[Event] = []

        # -----------------------
        # Fuel low
        # -----------------------
        if getattr(getattr(st, "status", None), "value", None) and getattr(getattr(st, "lap", None), "value", None):
            fuel_rem = float(st.status.value.fuel_remaining_laps)
            pen = float(st.lap.value.penalties_s)

            if pen == 0.0:
                crit = self.cfg.threshold("fuel_rem_laps_critical", 1.0)
                low = self.cfg.threshold("fuel_rem_laps_low", 2.0)

                if fuel_rem <= crit:
                    events.append(
                        Event(
                            key="fuel_low",
                            priority=Priority.IMMEDIATE_RISK,
                            urgency=1,
                            cooldown_s=self.cfg.cooldown("fuel_low", 25.0),
                            text=f"Combustible crítico: {fuel_rem:.2f} vueltas restantes.",
                        )
                    )
                elif fuel_rem <= low:
                    events.append(
                        Event(
                            key="fuel_low",
                            priority=Priority.MANAGEMENT,
                            urgency=0,
                            cooldown_s=self.cfg.cooldown("fuel_low", 25.0),
                            text=f"Combustible bajo: {fuel_rem:.2f} vueltas restantes.",
                        )
                    )

        # -----------------------
        # Wing damage
        # -----------------------
        if getattr(getattr(st, "damage", None), "value", None):
            dm = st.damage.value
            wing_max = max(float(dm.front_left_wing), float(dm.front_right_wing))
            warn = self.cfg.threshold("wing_damage_warn_pct", 25.0)
            crit = self.cfg.threshold("wing_damage_critical_pct", 60.0)

            if wing_max >= crit:
                events.append(
                    Event(
                        key="wing_damage",
                        priority=Priority.IMMEDIATE_RISK,
                        urgency=1,
                        cooldown_s=self.cfg.cooldown("wing_damage", 30.0),
                        text=f"Alerón delantero muy dañado: {wing_max:.0f}%",
                    )
                )
            elif wing_max >= warn:
                events.append(
                    Event(
                        key="wing_damage",
                        priority=Priority.MANAGEMENT,
                        urgency=0,
                        cooldown_s=self.cfg.cooldown("wing_damage", 30.0),
                        text=f"Alerón delantero dañado: {wing_max:.0f}%",
                    )
                )

        # -----------------------
        # Safety Car / VSC (Session.safety_car_status)
        # -----------------------
        events.extend(self._detect_sc_vsc(st))

        return events

    def _pit_hint(self, st, kind: str) -> str:
        """Heurística simple (sin gaps) para sugerir boxes durante SC/VSC."""
        reasons: list[str] = []

        status_val = getattr(getattr(st, "status", None), "value", None)
        damage_val = getattr(getattr(st, "damage", None), "value", None)

        # tyre age
        tyre_age = None
        if status_val is not None:
            tyre_age = getattr(status_val, "tyre_age_laps", None)
        if isinstance(tyre_age, (int, float)):
            k = "pit_tyres_age_sc" if kind == "SC" else "pit_tyres_age_vsc"
            thr_age = self.cfg.threshold(k, 10.0 if kind == "SC" else 12.0)
            if float(tyre_age) >= float(thr_age):
                reasons.append(f"neumáticos con {int(tyre_age)} vueltas")

        # tyre wear (si viene en damage packet)
        if damage_val is not None:
            wear = getattr(damage_val, "wear", None) or []
            try:
                wear_max = float(max(wear)) if wear else 0.0
            except Exception:
                wear_max = 0.0
            k = "pit_wear_sc" if kind == "SC" else "pit_wear_vsc"
            thr_wear = self.cfg.threshold(k, 30.0 if kind == "SC" else 40.0)
            if wear_max >= float(thr_wear):
                reasons.append(f"desgaste {wear_max:.0f}%")

            # wing
            wing_max = max(float(getattr(damage_val, "front_left_wing", 0.0)), float(getattr(damage_val, "front_right_wing", 0.0)))
            warn = self.cfg.threshold("wing_damage_warn_pct", 25.0)
            if wing_max >= warn:
                reasons.append(f"alerón {wing_max:.0f}%")

        if reasons:
            return "Considerá boxes: " + ", ".join(reasons) + "."
        return "Evaluá boxes según posición/gap; bajo " + kind + " suele ser buena oportunidad si estás cerca de tu ventana."

    def _detect_sc_vsc(self, st) -> list[Event]:
        sess_val = getattr(getattr(st, "session", None), "value", None)
        if sess_val is None:
            return []

        try:
            sc_code = int(getattr(sess_val, "safety_car_status", 0) or 0)
        except Exception:
            sc_code = 0

        if sc_code == self._last_sc_status:
            return []

        prev = self._last_sc_status
        self._last_sc_status = sc_code

        # track last active type (SC vs VSC), ignore ENDING/FORM as "type"
        if sc_code in (1, 2):
            self._last_active_sc = sc_code

        # resolve kind string for messaging
        kind = "SC" if self._last_active_sc == 1 else ("VSC" if self._last_active_sc == 2 else "SC/VSC")

        # DEPLOYED
        if sc_code in (1, 2):
            kind = "SC" if sc_code == 1 else "VSC"
            txt = f"{kind} desplegado. {self._pit_hint(st, kind)}"
            return [
                Event(
                    key=f"{kind.lower()}_deployed",
                    priority=Priority.STRATEGY_OPPORTUNITY,
                    urgency=1,
                    cooldown_s=self.cfg.cooldown("sc_vsc_deployed", 6.0),
                    text=txt,
                )
            ]

        # ENDING (prepare to restart)
        if sc_code == 4:
            txt = f"{kind} terminando: preparate para el relanzamiento (temperatura de gomas, delta, mapa)."
            return [
                Event(
                    key=f"{kind.lower()}_ending",
                    priority=Priority.STRATEGY_OPPORTUNITY,
                    urgency=1,
                    cooldown_s=self.cfg.cooldown("sc_vsc_ending", 4.0),
                    text=txt,
                )
            ]

        # FORMATION LAP (optional info)
        if sc_code == 3:
            return [
                Event(
                    key="formation_lap",
                    priority=Priority.INFO,
                    urgency=0,
                    cooldown_s=self.cfg.cooldown("formation_lap", 30.0),
                    text="Vuelta de formación.",
                )
            ]

        # CLEARED (back to green)
        if sc_code == 0 and prev in (1, 2, 4, 3):
            txt = f"Pista en verde: {kind} finalizado."
            return [
                Event(
                    key=f"{kind.lower().replace('/', '_')}_cleared",
                    priority=Priority.INFO,
                    urgency=0,
                    cooldown_s=self.cfg.cooldown("sc_vsc_cleared", 6.0),
                    text=txt,
                )
            ]

        return []