from __future__ import annotations

from pathlib import Path

def patch_cli(cli_path: Path) -> bool:
    txt = cli_path.read_text(encoding="utf-8")
    if "--rules-path" in txt and "--no-engine" in txt:
        return False

    lines = txt.splitlines(True)
    idx = None
    for i, line in enumerate(lines):
        if "--state-interval" in line:
            # avanzar hasta cerrar llamada add_argument (busca ')')
            j = i
            while j < len(lines) and ")" not in lines[j]:
                j += 1
            idx = j + 1
            break

    if idx is None:
        print("WARN: no encontré --state-interval en cli.py, no pude inyectar args de engine.")
        return False

    ins = []
    ins.append('\n')
    ins.append('    ap.add_argument("--no-engine", action="store_true", help="Disable rules/priority engine")\n')
    ins.append('    ap.add_argument("--rules-path", type=str, default="rules/v1.json", help="Rules JSON path")\n')
    ins.append('    ap.add_argument("--comm-throttle", type=float, default=0.0, help="Override throttle seconds (0=rules)")\n')

    lines[idx:idx] = ins
    cli_path.write_text("".join(lines), encoding="utf-8")
    print("OK: cli.py patched (engine args).")
    return True

def patch_app(app_path: Path) -> bool:
    txt = app_path.read_text(encoding="utf-8")

    # imports
    need_imports = [
        "from ingenierof125.engine.engine import EngineerEngine",
        "from ingenierof125.rules.load import load_rules, default_rules_path",
        "from ingenierof125.comms.logger_sink import LoggerComms",
    ]
    changed = False
    if "EngineerEngine" not in txt:
        # inserta imports cerca del resto de imports (después de los imports propios si se puede)
        lines = txt.splitlines(True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        for imp in need_imports:
            lines.insert(insert_at, imp + "\n")
            insert_at += 1
        lines.insert(insert_at, "\n")
        txt = "".join(lines)
        changed = True

    if "_engine_loop" not in txt:
        txt += """

async def _engine_loop(state_mgr, engine, interval_s: float) -> None:
    import asyncio

    interval = max(0.2, float(interval_s))
    while True:
        await asyncio.sleep(interval)
        # leer estado de forma tolerante
        st = getattr(state_mgr, "state", None)
        if st is None and hasattr(state_mgr, "get_state"):
            st = state_mgr.get_state()
        if st is None:
            continue
        t = getattr(st, "latest_session_time", -1.0)
        engine.tick(st, float(t))
"""
        changed = True

    # insertar init y task creation si encontramos StateManager(...)
    if "engine_task" not in txt:
        lines = txt.splitlines(True)
        # encuentra la primera asignación que contenga StateManager(
        sm_line = None
        for i, line in enumerate(lines):
            if "StateManager(" in line:
                sm_line = i
                break

        if sm_line is None:
            print("WARN: no encontré StateManager( en app.py, no pude auto-integrar engine loop.")
            if changed:
                app_path.write_text("".join(lines), encoding="utf-8")
                print("OK: app.py updated with imports/engine_loop only.")
            return changed

        # inserta unos renglones después de esa asignación
        ins = []
        ins.append("\n")
        ins.append("    engine_task = None\n")
        ins.append("    engine = None\n")
        ins.append("    try:\n")
        ins.append("        if (not getattr(args, 'no_engine', False)) and float(getattr(args, 'state_interval', 0) or 0) > 0:\n")
        ins.append("            rules_path = getattr(args, 'rules_path', None) or str(default_rules_path())\n")
        ins.append("            cfg = load_rules(rules_path)\n")
        ins.append("            override = float(getattr(args, 'comm_throttle', 0) or 0)\n")
        ins.append("            cfg = cfg.override(throttle_s=override)\n")
        ins.append("            engine = EngineerEngine.create(cfg, LoggerComms())\n")
        ins.append("            engine_task = asyncio.create_task(_engine_loop(state_mgr, engine, float(getattr(args, 'state_interval'))))\n")
        ins.append("    except Exception:\n")
        ins.append("        import logging\n")
        ins.append("        logging.getLogger('ingenierof125').exception('Engine init failed (continuing without engine)')\n")
        ins.append("\n")

        lines[sm_line+1:sm_line+1] = ins
        txt = "".join(lines)
        changed = True

    app_path.write_text(txt, encoding="utf-8")
    if changed:
        print("OK: app.py patched (engine loop).")
    return changed

def main() -> int:
    root = Path.cwd()
    cli = root / "ingenierof125" / "cli.py"
    app = root / "ingenierof125" / "app.py"
    ok = False
    if cli.exists():
        ok = patch_cli(cli) or ok
    else:
        print("WARN: no encontré ingenierof125/cli.py")

    if app.exists():
        ok = patch_app(app) or ok
    else:
        print("WARN: no encontré ingenierof125/app.py")

    return 0 if ok else 0

if __name__ == "__main__":
    raise SystemExit(main())
