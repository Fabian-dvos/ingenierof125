from __future__ import annotations

import json
from pathlib import Path

from ingenierof125.rules.model import RuleConfig


def default_rules_path() -> Path:
    # asumimos ejecutar desde la raíz del repo
    return Path.cwd() / "rules" / "v1.json"


def load_rules(path: str | Path) -> RuleConfig:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("rules json inválido (root no es objeto)")

    version = str(raw.get("version", "v1"))
    comms = raw.get("comms", {}) or {}
    th = float(comms.get("throttle_seconds", 12.0))

    cooldowns = raw.get("cooldowns", {}) or {}
    if not isinstance(cooldowns, dict):
        raise ValueError("cooldowns debe ser objeto")

    thresholds = raw.get("thresholds", {}) or {}
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds debe ser objeto")

    # normalizar a float
    cd = {str(k): float(v) for k, v in cooldowns.items()}
    tr = {str(k): float(v) for k, v in thresholds.items()}

    return RuleConfig(version=version, comms_throttle_s=th, event_cooldown_s=cd, thresholds=tr)
