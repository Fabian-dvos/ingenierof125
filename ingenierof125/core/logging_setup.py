from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def _level_from_str(s: str) -> int:
    s = (s or "INFO").upper().strip()
    return getattr(logging, s, logging.INFO)


def setup_logging(cfg: Any) -> None:
    """
    Configura logging de forma tolerante:
    - Si cfg no tiene log_dir/log_level, usa defaults seguros.
    - No rompe si el file handler falla (queda consola).
    - Evita duplicar handlers si se llama más de una vez.
    """
    log_dir = getattr(cfg, "log_dir", None) or "logs"
    log_level = getattr(cfg, "log_level", None) or "INFO"

    # Guardar defaults de vuelta en cfg para el resto del sistema
    try:
        cfg.log_dir = log_dir
        cfg.log_level = log_level
    except Exception:
        pass

    level = _level_from_str(log_level)

    root = logging.getLogger()
    root.setLevel(level)

    # Si ya está configurado, no duplicar
    already = {type(h) for h in root.handlers}

    # Consola
    if logging.StreamHandler not in already:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(sh)

    # Archivo (best-effort)
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        log_path = str(Path(log_dir) / "ingenierof125.log")

        # Evitar duplicar si ya hay file handler
        has_file = any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        if not has_file:
            fh = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
            root.addHandler(fh)
    except Exception:
        # Si no se pudo log a archivo, seguimos solo con consola
        root.exception("Logging file handler failed; continuing with console-only logs")
