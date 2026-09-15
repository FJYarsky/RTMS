# ==============================================================================
# RTMS v2.2.3 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger("rtms.autostart")

def get_startup_path() -> Path:
    appdata = os.getenv("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "rtms_startup.cmd"

BATCH_NAME = "rtms_startup.cmd"

def get_launch_command() -> tuple[str, str]:
    """Retorna (workdir, command_line) para iniciar RTMS sin ventana de consola."""
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        exe_dir = os.path.dirname(exe_path)
        return exe_dir, f'start "" "{exe_path}"'
    else:
        # En modo script, usar pythonw.exe del entorno local para no abrir consola
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        embedded_pythonw = os.path.join(base_dir, "bin", "python", "pythonw.exe")
        if os.path.exists(embedded_pythonw):
            python_bin = embedded_pythonw
        else:
            python_bin = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

        main_script = os.path.join(base_dir, "main.py")
        return base_dir, f'start "" "{python_bin}" "{main_script}"'

def _ensure_startup_dir() -> None:
    try:
        get_startup_path().parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create Startup directory: {e}")
        raise

def _write_batch_file() -> None:
    exe_dir, cmd = get_launch_command()
    # Batch que lanza el proceso con start "" en background y sale de inmediato sin quedarse abierto
    content = f'@echo off\ncd /d "{exe_dir}"\n{cmd}\nexit\n'
    p = get_startup_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Autostart batch created at {p}")
    except Exception as e:
        logger.error(f"Failed to write autostart batch: {e}")
        raise

def _remove_batch_file() -> None:
    p = get_startup_path()
    try:
        if p.is_file():
            p.unlink()
            logger.info(f"Autostart batch removed from {p}")
    except Exception as e:
        logger.error(f"Failed to remove autostart batch: {e}")
        raise

def enable_autostart(enable: bool) -> None:
    _ensure_startup_dir()
    if enable:
        _write_batch_file()
    else:
        _remove_batch_file()
    logger.debug(f"Autostart set to {'enabled' if enable else 'disabled'}")

def is_autostart_enabled() -> bool:
    return get_startup_path().is_file()
