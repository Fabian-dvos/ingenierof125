from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RuleConfig:
    """Config final para el motor.

    Nota: el motor necesita valores materializados (throttle/cooldowns/thresholds).
    """

    version: str = "v1"
    comms_throttle_s: float = 12.0
    event_cooldown_s: Mapping[str, float] = field(default_factory=dict)
    thresholds: Mapping[str, float] = field(default_factory=dict)

    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        raw = self.raw or {}
        if not raw:
            return

        # version
        if self.version == "v1" and "version" in raw:
            try:
                object.__setattr__(self, "version", str(raw.get("version") or "v1"))
            except Exception:
                pass

        # comms throttle: nuevo y legado
        if self.comms_throttle_s == 12.0:
            try:
                comms = raw.get("comms") or {}
                v = raw.get("comms_throttle_s", None)
                if v is None:
                    v = raw.get("throttle_s", None)
                if v is None:
                    v = comms.get("throttle_s", None)
                if v is None:
                    v = comms.get("throttle_seconds", None)
                if v is not None:
                    object.__setattr__(self, "comms_throttle_s", float(v))
            except Exception:
                pass

        # cooldowns: 'event_cooldown_s' (nuevo) o 'cooldowns' (legado)
        if not self.event_cooldown_s:
            try:
                cd = raw.get("event_cooldown_s") or raw.get("cooldowns") or {}
                object.__setattr__(self, "event_cooldown_s", dict(cd))
            except Exception:
                pass

        # thresholds
        if not self.thresholds:
            try:
                th = raw.get("thresholds") or {}
                object.__setattr__(self, "thresholds", dict(th))
            except Exception:
                pass

        # aliases (legado -> nuevo)
        try:
            th = dict(self.thresholds or {})
            if "wing_damage_warn_pct" not in th and "wing_damage_warn" in th:
                th["wing_damage_warn_pct"] = float(th["wing_damage_warn"])
            if "wing_damage_critical_pct" not in th and "wing_damage_critical" in th:
                th["wing_damage_critical_pct"] = float(th["wing_damage_critical"])
            object.__setattr__(self, "thresholds", th)
        except Exception:
            pass

    def cooldown(self, key: str, default: float) -> float:
        try:
            return float(self.event_cooldown_s.get(key, default))
        except Exception:
            return float(default)

    def threshold(self, key: str, default: float) -> float:
        if key not in self.thresholds:
            alias = {
                "wing_damage_warn_pct": "wing_damage_warn",
                "wing_damage_critical_pct": "wing_damage_critical",
            }
            if key in alias and alias[key] in self.thresholds:
                key = alias[key]

        try:
            return float(self.thresholds.get(key, default))
        except Exception:
            return float(default)


@dataclass(frozen=True, slots=True)
class RulesConfig:
    version: str
    raw: Mapping[str, Any]

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "RulesConfig":
        v = str(raw.get("version", "v1"))
        return RulesConfig(version=v, raw=raw)

    def override(self, *, throttle_s: float | None = None) -> "RulesConfig":
        new = dict(self.raw)

        if throttle_s is not None:
            # nuevo
            new["comms_throttle_s"] = float(throttle_s)
            # legado
            comms = dict(new.get("comms") or {})
            comms["throttle_seconds"] = float(throttle_s)
            comms["throttle_s"] = float(throttle_s)
            new["comms"] = comms

        return RulesConfig(version=self.version, raw=new)

    @property
    def comms_throttle_s(self) -> float:
        if "comms_throttle_s" in self.raw:
            return float(self.raw.get("comms_throttle_s", 12.0))

        comms = self.raw.get("comms") or {}
        if "throttle_s" in comms:
            return float(comms.get("throttle_s", 12.0))
        if "throttle_seconds" in comms:
            return float(comms.get("throttle_seconds", 12.0))

        return float(self.raw.get("throttle_s", 12.0))

    @property
    def cooldowns(self) -> Mapping[str, float]:
        cd = self.raw.get("event_cooldown_s")
        if isinstance(cd, dict):
            return cd
        cd = self.raw.get("cooldowns")
        if isinstance(cd, dict):
            return cd
        return {}

    @property
    def thresholds(self) -> Mapping[str, float]:
        thr = self.raw.get("thresholds")
        return thr if isinstance(thr, dict) else {}

    def as_rule_config(self) -> RuleConfig:
        return RuleConfig(
            version=self.version,
            comms_throttle_s=self.comms_throttle_s,
            event_cooldown_s=dict(self.cooldowns),
            thresholds=dict(self.thresholds),
            raw=self.raw,
        )