# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.2
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger("rtms.autostart")

STARTUP_DIR = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
BATCH_NAME = "rtms_startup.cmd"
BATCH_PATH = STARTUP_DIR / BATCH_NAME

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
            python_bin = sys.executable.replace("python.exe", "pythonw.exe")
        
        main_script = os.path.join(base_dir, "main.py")
        return base_dir, f'start "" "{python_bin}" "{main_script}"'

def _ensure_startup_dir() -> None:
    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create Startup directory: {e}")
        raise

def _write_batch_file() -> None:
    exe_dir, cmd = get_launch_command()
    # Batch que lanza el proceso con start "" en background y sale de inmediato sin quedarse abierto
    content = f'@echo off\ncd /d "{exe_dir}"\n{cmd}\nexit\n'
    try:
        with open(BATCH_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Autostart batch created at {BATCH_PATH}")
    except Exception as e:
        logger.error(f"Failed to write autostart batch: {e}")
        raise

def _remove_batch_file() -> None:
    try:
        if BATCH_PATH.is_file():
            BATCH_PATH.unlink()
            logger.info(f"Autostart batch removed from {BATCH_PATH}")
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
    return BATCH_PATH.is_file()
