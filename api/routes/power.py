# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de gestión y optimización de energía Win32.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para control y auditoría de perfiles energéticos nativos de Windows."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_token
from core.system_env import BACKUP_FILE, restore_original_power_settings, setup_windows_environment

logger = logging.getLogger("rtms.api.power")
router = APIRouter()


@router.get("/api/power/status", dependencies=[Depends(verify_api_token)])
async def power_status():
    """Retorna si las optimizaciones de energía están aplicadas actualmente."""
    return {"optimizations_applied": os.path.exists(BACKUP_FILE)}


@router.post("/api/power/apply", dependencies=[Depends(verify_api_token)])
async def apply_power():
    """Aplica las optimizaciones de energía y estabilidad en Windows y reporta el resultado real."""
    result = setup_windows_environment()
    return result


@router.post("/api/power/restore", dependencies=[Depends(verify_api_token)])
async def restore_power():
    """Restaura la configuración original de energía de Windows (Protegido por Token)."""
    result = restore_original_power_settings()
    if result.get("status") == "ok":
        return result
    raise HTTPException(status_code=400, detail=result.get("message", "Error al restaurar"))
