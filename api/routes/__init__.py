# ==============================================================================
# RTMS — Real-Time Multicam System
# Ensamblado del enrutador principal de la API REST.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Paquete de rutas REST de RTMS ensamblado a partir de sub-routers modulares."""

from fastapi import APIRouter

from .config import router as config_router
from .health import router as health_router
from .power import router as power_router
from .preview import router as preview_router
from .streams import router as streams_router
from .system import router as system_router

router = APIRouter()

router.include_router(health_router)
router.include_router(streams_router)
router.include_router(preview_router)
router.include_router(config_router)
router.include_router(system_router)
router.include_router(power_router)

__all__ = ["router"]
