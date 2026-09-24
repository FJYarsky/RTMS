# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de importación, exportación y respaldo de configuración.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para exportación segura y restauración de configuraciones del sistema."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from api.deps import verify_api_token
from api.schemas import FullExportRequest, ImportConfigRequest
from core.config_mgr import export_config, import_config, load_config
from core.hardware_sync import sync_streams_with_hardware
from core.stream_manager import stream_manager

logger = logging.getLogger("rtms.api.config")
router = APIRouter()


@router.get("/api/config/export", dependencies=[Depends(verify_api_token)])
async def export_config_endpoint():
    """Exporta la configuración completa para respaldo o migración (con secretos enmascarados en GET)."""
    return await asyncio.to_thread(export_config, safe_mode=True)


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
    return await asyncio.to_thread(export_config, safe_mode=False)


@router.post("/api/config/import", dependencies=[Depends(verify_api_token)])
async def import_config_endpoint(payload: ImportConfigRequest):
    """Importa una configuración externa completa previa validación de esquema y reinicia selectivamente flujos afectados."""
    # 1. Registrar estado y parámetros de flujos activos antes de la importación
    running_before = {dp: dict(proc.config) for dp, proc in stream_manager._procs.items() if proc.is_alive}

    # 2. Persistir configuración de forma asíncrona
    success = await asyncio.to_thread(import_config, payload.config_data)
    if not success:
        raise HTTPException(status_code=400, detail="Estructura de configuración inválida")

    # 3. Sincronizar dispositivos de hardware
    try:
        await sync_streams_with_hardware()
    except Exception as e:
        logger.warning(f"Error sincronizando hardware tras importación de config: {e}")

    # 4. Reiniciar únicamente los streams que estaban corriendo y cuyos parámetros de pipeline cambiaron
    new_cfg = await asyncio.to_thread(load_config)
    new_cams = new_cfg.get("cameras", {})
    pipeline_keys = {
        "resolution",
        "fps",
        "bitrate",
        "protocol",
        "encoder",
        "port",
        "srt_latency",
        "srt_passphrase",
        "zerolatency",
        "udp_mode",
        "udp_host",
    }

    for dp, old_cam_cfg in running_before.items():
        new_cam_cfg = new_cams.get(dp)
        if not new_cam_cfg:
            # Cámara fue eliminada en la nueva config
            await stream_manager.stop_stream(dp)
            continue
        changed = any(old_cam_cfg.get(k) != new_cam_cfg.get(k) for k in pipeline_keys)
        if changed:
            logger.info(f"Parámetros de pipeline de '{dp}' cambiaron tras importación. Reiniciando flujo...")
            await stream_manager.restart_stream(dp)

    return {"status": "ok", "message": "Configuración importada y aplicada exitosamente"}
