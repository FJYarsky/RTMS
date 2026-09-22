# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de importación, exportación y respaldo de configuración.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para exportación segura y restauración de configuraciones del sistema."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from api.deps import verify_api_token
from api.schemas import FullExportRequest, ImportConfigRequest
from core.config_mgr import export_config, import_config
from core.hardware_sync import sync_streams_with_hardware

logger = logging.getLogger("rtms.api.config")
router = APIRouter()


@router.get("/api/config/export", dependencies=[Depends(verify_api_token)])
async def export_config_endpoint(safe_mode: bool = True):
    """Exporta la configuración completa para respaldo o migración (con secretos enmascarados en GET)."""
    return export_config(safe_mode=True)


@router.post("/api/config/export/full", dependencies=[Depends(verify_api_token)])
async def export_full_config_endpoint(payload: FullExportRequest, response: Response):
    """
    Exporta la configuración completa incluyendo contraseñas sin enmascarar.
    Requiere confirmación explícita mediante confirm_export_secrets=True en el cuerpo.
    """
    if not payload.confirm_export_secrets:
        raise HTTPException(
            status_code=400,
            detail="Debe confirmar explícitamente la exportación de secretos con confirm_export_secrets=True.",
        )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return export_config(safe_mode=False)


@router.post("/api/config/import", dependencies=[Depends(verify_api_token)])
async def import_config_endpoint(payload: ImportConfigRequest):
    """Importa una configuración externa completa previa validación de esquema."""
    success = import_config(payload.config_data)
    if not success:
        raise HTTPException(status_code=400, detail="Estructura de configuración inválida")
    try:
        await sync_streams_with_hardware()
    except Exception as e:
        logger.warning(f"Error sincronizando hardware tras importación de config: {e}")
    return {"status": "ok", "message": "Configuración importada y aplicada exitosamente"}
