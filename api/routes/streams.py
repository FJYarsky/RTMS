# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de gestión de flujos de video, configuración y hardware.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para inicio, parada, configuración y estado de streams de video."""

import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.deps import get_local_ip, verify_api_token
from api.schemas import (
    ApplyPresetRequest,
    CameraAutostartToggle,
    CameraConfigUpdate,
    StreamAction,
)
from core.__version__ import __version__
from core.autostart import is_autostart_enabled
from core.config_mgr import (
    CAMERA_PRESETS,
    apply_camera_preset,
    find_camera_by_id_or_path,
    set_camera_autostart,
    update_camera_config,
)
from core.hardware_sync import get_all_stream_statuses, sync_streams_with_hardware
from core.stream_manager import stream_manager

logger = logging.getLogger("rtms.api.streams")
router = APIRouter()


@router.get("/api/status", dependencies=[Depends(verify_api_token)])
async def get_status():
    """Retorna el estado general del sistema, IP local y flujos con contraseñas enmascaradas."""
    raw_streams = get_all_stream_statuses()

    # Seguridad: Enmascarar srt_passphrase para no exponerla en texto plano
    sanitized_streams = []
    for s in raw_streams:
        sc = dict(s)
        real_pass = sc.get("srt_passphrase", "")
        sc["has_passphrase"] = bool(real_pass)
        sc["srt_passphrase"] = "••••••••" if real_pass else ""
        sanitized_streams.append(sc)

    from core.system_env import get_platform_details

    return {
        "version": __version__,
        "local_ip": get_local_ip(),
        "platform_info": get_platform_details(),
        "autostart_enabled": is_autostart_enabled(),
        "streams": sanitized_streams,
        "presets": {k: v["name"] for k, v in CAMERA_PRESETS.items()},
    }


@router.post("/api/stream/action", dependencies=[Depends(verify_api_token)])
async def handle_stream_action(action: StreamAction):
    """Inicia, detiene o reinicia un flujo manualmente por device_path o camera_id."""
    cam = find_camera_by_id_or_path(action.device_path)
    dp = cam["device_path"] if cam else action.device_path

    if action.action == "stop":
        await stream_manager.stop_stream(dp)
        return {"status": "ok", "message": "Flujo detenido"}

    elif action.action == "start":
        proc = stream_manager.get_proc(dp)
        if proc:
            await stream_manager.start_stream(dp)
            return {"status": "ok", "message": "Flujo iniciado"}
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado en el registro")

    elif action.action == "restart":
        proc = stream_manager.get_proc(dp)
        if proc:
            await stream_manager.stop_stream(dp)
            await stream_manager.start_stream(dp)
            return {"status": "ok", "message": "Flujo reiniciado"}
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado en el registro")

    raise HTTPException(status_code=400, detail="Acción inválida")


@router.post("/api/stream/config", dependencies=[Depends(verify_api_token)])
async def update_stream_config_endpoint(config: CameraConfigUpdate):
    """Actualiza la configuración de una cámara (Protegido por Token)."""
    cam = find_camera_by_id_or_path(config.device_path)
    dp = cam["device_path"] if cam else config.device_path

    # Si la contraseña enviada es la enmascarada "••••••••", preservar la existente
    passphrase_to_set = config.srt_passphrase
    proc = stream_manager.get_proc(dp)
    if passphrase_to_set == "••••••••":
        if proc and proc.config:
            passphrase_to_set = proc.config.get("srt_passphrase", "")
        elif cam:
            passphrase_to_set = cam.get("srt_passphrase", "")

    saved = update_camera_config(
        device_path=dp,
        resolution=config.resolution,
        fps=config.fps,
        bitrate=config.bitrate,
        protocol=config.protocol or "srt",
        encoder=config.encoder or "auto",
        srt_latency=config.srt_latency or 120,
        srt_passphrase=passphrase_to_set or "",
        auto_start=config.auto_start,
        zerolatency=config.zerolatency if config.zerolatency is not None else True,
        is_virtual=config.is_virtual if config.is_virtual is not None else False,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Error al persistir la configuración de la cámara en disco.")

    if proc:
        proc.config["resolution"] = config.resolution
        proc.config["fps"] = config.fps
        proc.config["bitrate"] = config.bitrate
        proc.config["protocol"] = config.protocol or "srt"
        proc.config["encoder"] = config.encoder or "auto"
        proc.config["srt_latency"] = config.srt_latency or 120
        proc.config["srt_passphrase"] = passphrase_to_set or ""
        if config.auto_start is not None:
            proc.config["auto_start"] = config.auto_start
        if config.zerolatency is not None:
            proc.config["zerolatency"] = config.zerolatency
        if config.is_virtual is not None:
            proc.config["is_virtual"] = config.is_virtual

        if proc.is_alive:
            await stream_manager.stop_stream(dp)
            await stream_manager.start_stream(dp)

    return {"status": "ok", "message": "Configuración guardada y aplicada"}


@router.delete("/api/stream/{device_path:path}", dependencies=[Depends(verify_api_token)])
async def delete_camera_endpoint(device_path: str):
    """Elimina una cámara de la configuración persistida y detiene su proceso asociado."""
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path

    # Detener stream y eliminar de configuración persistida
    removed = await stream_manager.remove_stream(dp)
    if not removed and cam and "camera_id" in cam:
        removed = await stream_manager.remove_stream(cam["camera_id"])

    if not removed:
        raise HTTPException(status_code=404, detail="Cámara no encontrada en la configuración")

    return {"status": "ok", "message": f"Cámara {dp} eliminada permanentemente"}


@router.post("/api/stream/preset", dependencies=[Depends(verify_api_token)])
async def apply_preset_endpoint(payload: ApplyPresetRequest):
    """Aplica un perfil predefinido a una cámara existente."""
    cam = find_camera_by_id_or_path(payload.device_path)
    dp = cam["device_path"] if cam else payload.device_path

    updated_cam = apply_camera_preset(dp, payload.preset_key)
    if not updated_cam:
        raise HTTPException(
            status_code=404, detail="Perfil o cámara no encontrados, o error al persistir configuración."
        )

    proc = stream_manager.get_proc(dp)
    if proc:
        proc.config.update(updated_cam)
        if proc.is_alive:
            await stream_manager.stop_stream(dp)
            await stream_manager.start_stream(dp)

    return {"status": "ok", "message": f"Perfil aplicado exitosamente a {dp}", "camera": updated_cam}


@router.post("/api/stream/autostart_toggle", dependencies=[Depends(verify_api_token)])
async def toggle_cam_autostart(payload: CameraAutostartToggle):
    """Activa o desactiva el autoarranque desatendido de una cámara individual (Protegido por Token)."""
    cam = find_camera_by_id_or_path(payload.device_path)
    dp = cam["device_path"] if cam else payload.device_path

    saved = set_camera_autostart(dp, payload.auto_start)
    if not saved:
        raise HTTPException(status_code=500, detail="Error al persistir el estado de autoarranque en disco.")

    proc = stream_manager.get_proc(dp)
    if proc and proc.config:
        proc.config["auto_start"] = payload.auto_start
    return {"status": "ok", "auto_start": payload.auto_start}


@router.post("/api/hardware/scan", dependencies=[Depends(verify_api_token)])
async def scan_hardware():
    """Fuerza un sondeo completo de hardware DirectShow (Protegido por Token)."""
    await sync_streams_with_hardware()
    return {"status": "ok", "message": "Escaneo de hardware completado"}


@router.get("/api/stream/logs", dependencies=[Depends(verify_api_token)])
async def get_stream_logs(device_path: str):
    """Retorna los logs sanitizados de FFmpeg del flujo solicitado (Protegido por Token)."""
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path

    proc = stream_manager.get_proc(dp)
    if not proc:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"logs": proc.get_logs()}


@router.get("/api/stream/{device_path:path}/connect_url", dependencies=[Depends(verify_api_token)])
async def get_stream_connect_url(device_path: str):
    """Retorna la URL normalizada completa para que clientes externos (OBS/vMix) se conecten directamente."""
    cam = find_camera_by_id_or_path(device_path)
    if not cam:
        raise HTTPException(status_code=404, detail="Dispositivo de cámara no encontrado")

    dp = cam["device_path"]
    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else cam

    protocol = cfg.get("protocol", "srt")
    port = cfg.get("port", 9000)
    raw_pass = cfg.get("srt_passphrase", "")
    passphrase = ""
    if raw_pass:
        from core.secrets_mgr import unprotect_secret

        passphrase = unprotect_secret(raw_pass)
    latency = int(cfg.get("srt_latency", 120))
    local_ip = get_local_ip()

    if protocol == "srt":
        params = {"mode": "caller", "latency": str(latency * 1000)}
        if passphrase:
            params["passphrase"] = passphrase
        query = urllib.parse.urlencode(params)
        url = f"srt://{local_ip}:{port}?{query}"
    else:
        ip_last = (int(port) % 200) + 1
        url = f"udp://239.255.0.{ip_last}:{port}?pkt_size=1316"

    return JSONResponse(
        content={
            "status": "ok",
            "device_path": dp,
            "protocol": protocol,
            "connect_url": url,
            "has_passphrase": bool(passphrase),
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
