from __future__ import annotations

from typing import Any, Dict, Iterator, Mapping, Optional


class RulesConfig(Mapping[str, Any]):
    """
    Wrapper dict-like que sale de load_rules().
    Mantiene compatibilidad con tests y lectura flexible.
    """

    def __init__(self, raw: Optional[Mapping[str, Any]] = None) -> None:
        self.raw: Dict[str, Any] = dict(raw or {})

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)

    @property
    def version(self) -> str:
        return str(self.raw.get("version", "v1"))

    @property
    def comms_throttle_s(self) -> float:
        v = self.raw.get("comms_throttle_s", self.raw.get("throttle_s", 0.0))
        try:
            return float(v or 0.0)
        except Exception:
            return 0.0

    @property
    def event_cooldown_s(self) -> Dict[str, float]:
        cd = self.raw.get("event_cooldown_s", {}) or {}
        return dict(cd)

    @property
    def thresholds(self) -> Dict[str, Any]:
        th = self.raw.get("thresholds", {}) or {}
        return dict(th)

    def threshold(self, key: str, default: float) -> float:
        try:
            return float(self.thresholds.get(key, default))
        except Exception:
            return float(default)

    def cooldown(self, key: str, default: float) -> float:
        try:
            return float(self.event_cooldown_s.get(key, default))
        except Exception:
            return float(default)

    def override(self, **kwargs: Any) -> "RulesConfig":
        data = dict(self.raw)
        for k, v in kwargs.items():
            if k in ("throttle_s", "comms_throttle_s"):
                data["comms_throttle_s"] = float(v)
            else:
                data[k] = v
        return type(self)(data)


class RuleConfig(RulesConfig):
    """
    Objeto que espera el motor.
    Permite construcción directa (tests) y conserva el formato dict-like.
    """

    def __init__(
        self,
        *,
        version: Optional[str] = None,
        comms_throttle_s: Optional[float] = None,
        event_cooldown_s: Optional[Mapping[str, float]] = None,
        thresholds: Optional[Mapping[str, Any]] = None,
        raw: Optional[Mapping[str, Any]] = None,
        **extra: Any,
    ) -> None:
        data = dict(raw or {})
        if version is not None:
            data["version"] = version
        else:
            data.setdefault("version", "v1")

        if comms_throttle_s is not None:
            data["comms_throttle_s"] = float(comms_throttle_s)

        if event_cooldown_s is not None:
            data["event_cooldown_s"] = dict(event_cooldown_s)

        if thresholds is not None:
            data["thresholds"] = dict(thresholds)

        if extra:
            data.update(extra)

        super().__init__(data)