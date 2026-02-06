from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler, BaseRotatingHandler
from pathlib import Path
from typing import Any


def _level_from_str(s: str) -> int:
    s = (s or "INFO").upper().strip()
    return getattr(logging, s, logging.INFO)


def setup_logging(cfg: Any) -> None:
    """
    Logging robusto:
    - Defaults seguros si faltan atributos en cfg.
    - No duplica handlers si se llama más de una vez.
    - File handler es best-effort; si falla sigue consola.
    """
    log_dir = getattr(cfg, "log_dir", None) or "logs"
    log_level = getattr(cfg, "log_level", None) or "INFO"

    # Persistir defaults en cfg
    try:
        cfg.log_dir = log_dir
        cfg.log_level = log_level
    except Exception:
        pass

    level = _level_from_str(log_level)

    root = logging.getLogger()
    root.setLevel(level)

    # No duplicar handlers
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_stream:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(sh)

    # File handler (best-effort)
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        log_path = str(Path(log_dir) / "ingenierof125.log")

        # OJO: usar BaseRotatingHandler para que tests con mock no rompan isinstance
        has_file = any(isinstance(h, BaseRotatingHandler) for h in root.handlers)
        if not has_file:
            fh = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
            root.addHandler(fh)
    except Exception:
        root.exception("Logging file handler failed; continuing with console-only logs")
