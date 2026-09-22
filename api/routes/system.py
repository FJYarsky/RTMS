# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de control de sistema, métricas, apagado y restablecimiento.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para telemetría del sistema, parada de emergencia, reinicio y autostart."""

import json
import logging
import os
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_token
from api.schemas import AutostartToggle, FactoryResetRequest, SystemShutdownRequest
from core.__version__ import __version__
from core.hardware_sync import get_all_stream_statuses
from core.preview_mgr import preview_manager
from core.process_cleanup import terminate_all_processes
from core.stream_manager import stream_manager
from core.telemetry import telemetry_service

logger = logging.getLogger("rtms.api.system")
router = APIRouter()


@router.get("/api/system/metrics", dependencies=[Depends(verify_api_token)])
async def get_system_metrics():
    """Retorna métricas de hardware (CPU, GPU, RAM), red y telemetría de streams en vivo para el HUD."""
    statuses = get_all_stream_statuses()
    running_streams = [s for s in statuses if s["status"]["state"] == "running"]
    total_bitrate = sum(s["status"]["current_bitrate_kbps"] for s in running_streams)

    return telemetry_service.collect(
        active_streams_count=len(running_streams),
        total_bitrate_kbps=total_bitrate,
    )


@router.post("/api/system/emergency_stop", dependencies=[Depends(verify_api_token)])
@router.post("/api/system/global_stop", dependencies=[Depends(verify_api_token)])
async def emergency_stop():
    """Detiene inmediatamente todos los flujos de FFmpeg de forma ordenada y segura (Protegido por Token)."""
    await stream_manager.emergency_stop_all()
    return {"status": "ok", "message": "Todas las transmisiones activas fueron detenidas correctamente."}


@router.post("/api/system/shutdown", dependencies=[Depends(verify_api_token)])
async def system_shutdown(payload: Optional[SystemShutdownRequest] = None):
    """Finaliza totalmente la aplicación y todos sus subprocesos (FFmpeg, FFplay)."""
    force = payload.force if payload else True

    def _delayed_exit():
        time.sleep(0.5)
        terminate_all_processes(force=force)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "ok", "message": "RTMS finalizando todos los procesos y cerrando aplicación."}


@router.post("/api/system/factory_reset", dependencies=[Depends(verify_api_token)])
async def system_factory_reset(payload: FactoryResetRequest):
    """
    Restaura la configuración de fábrica, purga credenciales, logs, copias de seguridad
    y finaliza la aplicación para un restablecimiento limpio.
    """
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Debe confirmar explícitamente el restablecimiento de fábrica.")

    # 1. Detener todas las transmisiones activas
    await stream_manager.stop_all()
    await preview_manager.stop_all()

    # 2. Eliminar autostart de Windows si estaba activo
    try:
        from core.autostart import enable_autostart

        enable_autostart(False)
    except Exception as e:
        logger.debug(f"Aviso al deshabilitar autostart durante reset: {e}")

    # 3. Restaurar configuraciones de energía si existen
    try:
        from core.system_env import restore_original_power_settings

        restore_original_power_settings()
    except Exception:
        pass

    # 4. Limpiar archivos de configuración y logs
    from core.config_mgr import CONFIG_BAK_FILE, CONFIG_DIR, CONFIG_FILE, get_base_dir

    base_dir = get_base_dir()

    for fname in [CONFIG_FILE, CONFIG_BAK_FILE, os.path.join(CONFIG_DIR, "power_backup.json")]:
        try:
            if os.path.exists(fname):
                os.remove(fname)
        except Exception as e:
            logger.debug(f"Aviso eliminando {fname}: {e}")

    # Purgar logs en el directorio activo y en LOCALAPPDATA
    log_candidates = [
        os.path.join(base_dir, "rtms.log"),
        os.path.join(base_dir, "rtms.log.1"),
        os.path.join(base_dir, "rtms.log.2"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "RTMS", "rtms.log"),
    ]
    for log_candidate in log_candidates:
        try:
            if log_candidate and os.path.exists(log_candidate):
                os.remove(log_candidate)
        except Exception:
            pass

    # Recrear config.json inicial limpio
    try:
        clean_config = {
            "version": __version__,
            "config_schema_version": 4,
            "cameras": {},
            "ignored_devices": [],
            "next_port": 9000,
            "unattended_autostart": True,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_config, f, indent=4)
    except Exception as e:
        logger.error(f"Error reescribiendo configuración inicial limpia: {e}")

    def _delayed_exit():
        time.sleep(0.8)
        terminate_all_processes(force=True)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "ok", "message": "Datos eliminados y configuración restablecida. RTMS se cerrará ahora."}


@router.post("/api/autostart", dependencies=[Depends(verify_api_token)])
async def set_autostart(toggle: AutostartToggle):
    """Habilita o deshabilita el autoarranque de RTMS con Windows (Protegido por Token)."""
    from core.autostart import enable_autostart

    enable_autostart(toggle.enable)
    return {"status": "ok", "autostart": toggle.enable}
