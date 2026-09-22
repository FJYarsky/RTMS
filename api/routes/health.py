# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de comprobación de salud y disponibilidad.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas de observabilidad y probes de salud (/healthz, /readyz)."""

import logging

from fastapi import APIRouter, HTTPException

from core.__version__ import __version__
from core.preview_mgr import preview_manager

logger = logging.getLogger("rtms.api.health")
router = APIRouter()


@router.get("/healthz")
async def healthz():
    """Endpoint público de verificación de salud para supervisores externos de procesos."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
async def readyz():
    """Readiness probe para verificar que el backend y binarios multimedia están listos."""
    if not preview_manager.has_ffmpeg_binary():
        raise HTTPException(status_code=503, detail="Binario FFmpeg no disponible en el sistema.")
    return {"status": "ok", "ready": True, "ffmpeg": True}
