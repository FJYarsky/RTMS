# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de gestión de flujos de video, configuración y hardware.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para inicio, parada, configuración y estado de streams de video."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.deps import get_local_ip, verify_api_token
from api.schemas import (
    ApplyPresetRequest,
    CameraAutostartToggle,
    CameraConfigUpdate,
    DeviceUnignoreRequest,
    IgnoredDeviceItem,
    IgnoredDevicesResponse,
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

    from core.mediamtx_mgr import mediamtx_manager
    from core.system_env import get_platform_details

    return {
        "version": __version__,
        "local_ip": get_local_ip(),
        "mediamtx_srt_port": mediamtx_manager.get_srt_port(),
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
        if proc or cam:
            await stream_manager.start_stream(dp)
            return {"status": "ok", "message": "Flujo iniciado"}
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado en el registro")

    elif action.action == "restart":
        proc = stream_manager.get_proc(dp)
        if proc or cam:
            await stream_manager.restart_stream(dp)
            return {"status": "ok", "message": "Flujo reiniciado"}
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado en el registro")

    raise HTTPException(status_code=400, detail="Acción inválida")


@router.post("/api/stream/config", dependencies=[Depends(verify_api_token)])
async def update_stream_config_endpoint(config: CameraConfigUpdate):
    """Actualiza la configuración de una cámara con semántica PATCH (Protegido por Token)."""
    cam = find_camera_by_id_or_path(config.device_path)
    dp = cam["device_path"] if cam else config.device_path
    proc = stream_manager.get_proc(dp)

    existing_cfg = (cam or (proc.config if proc else {})).copy()

    # Resolver passphrase con soporte explícito de secret_action
    passphrase_to_set = existing_cfg.get("srt_passphrase", "")
    if config.secret_action == "clear":
        passphrase_to_set = ""
    elif config.secret_action == "set" or (config.secret_action is None and config.srt_passphrase is not None):
        if config.srt_passphrase != "••••••••":
            passphrase_to_set = config.srt_passphrase or ""
    elif config.secret_action == "keep" or config.srt_passphrase == "••••••••":
        passphrase_to_set = existing_cfg.get("srt_passphrase", "")

    # Semántica PATCH: preservar valores existentes si no vienen en el payload
    res = config.resolution if config.resolution is not None else existing_cfg.get("resolution", "720p")
    fps_val = config.fps if config.fps is not None else existing_cfg.get("fps", 30)
    bitrate_val = config.bitrate if config.bitrate is not None else existing_cfg.get("bitrate", 3000)
    proto_val = config.protocol if config.protocol is not None else existing_cfg.get("protocol", "srt")
    encoder_val = config.encoder if config.encoder is not None else existing_cfg.get("encoder", "auto")
    srt_latency_val = config.srt_latency if config.srt_latency is not None else existing_cfg.get("srt_latency", 120)
    auto_start_val = config.auto_start if config.auto_start is not None else existing_cfg.get("auto_start", False)
    zero_val = config.zerolatency if config.zerolatency is not None else existing_cfg.get("zerolatency", True)
    virtual_val = config.is_virtual if config.is_virtual is not None else existing_cfg.get("is_virtual", False)
    udp_mode_val = config.udp_mode if config.udp_mode is not None else existing_cfg.get("udp_mode", "multicast")
    udp_host_val = config.udp_host if config.udp_host is not None else existing_cfg.get("udp_host", "127.0.0.1")

    saved = await asyncio.to_thread(
        update_camera_config,
        device_path=dp,
        resolution=res,
        fps=fps_val,
        bitrate=bitrate_val,
        protocol=proto_val,
        encoder=encoder_val,
        srt_latency=srt_latency_val,
        srt_passphrase=passphrase_to_set,
        auto_start=auto_start_val,
        zerolatency=zero_val,
        is_virtual=virtual_val,
        udp_mode=udp_mode_val,
        udp_host=udp_host_val,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Error al persistir la configuración de la cámara en disco.")

    if proc:
        proc.config["resolution"] = res
        proc.config["fps"] = fps_val
        proc.config["bitrate"] = bitrate_val
        proc.config["protocol"] = proto_val
        proc.config["encoder"] = encoder_val
        proc.config["srt_latency"] = srt_latency_val
        proc.config["srt_passphrase"] = passphrase_to_set
        proc.config["udp_mode"] = udp_mode_val
        proc.config["udp_host"] = udp_host_val
        proc.config["auto_start"] = auto_start_val
        proc.config["zerolatency"] = zero_val
        proc.config["is_virtual"] = virtual_val

        if proc.is_alive:
            await stream_manager.restart_stream(dp)

    try:
        from core.mediamtx_mgr import mediamtx_manager

        mediamtx_manager.generate_config()
        await mediamtx_manager.sync_paths_api()
    except Exception as ex:
        logger.debug(f"Aviso regenerando configuración de MediaMTX tras guardar cámara: {ex}")

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

    try:
        from core.mediamtx_mgr import mediamtx_manager

        mediamtx_manager.generate_config()
        await mediamtx_manager.sync_paths_api()
    except Exception as ex:
        logger.debug(f"Aviso regenerando configuración de MediaMTX tras eliminar cámara: {ex}")

    return {"status": "ok", "message": f"Cámara {dp} eliminada permanentemente"}


@router.post("/api/stream/preset", dependencies=[Depends(verify_api_token)])
async def apply_preset_endpoint(payload: ApplyPresetRequest):
    """Aplica un perfil predefinido a una cámara existente."""
    cam = find_camera_by_id_or_path(payload.device_path)
    dp = cam["device_path"] if cam else payload.device_path

    updated_cam = await asyncio.to_thread(apply_camera_preset, dp, payload.preset_key)
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

    saved = await asyncio.to_thread(set_camera_autostart, dp, payload.auto_start)
    if not saved:
        raise HTTPException(status_code=500, detail="Error al persistir el estado de autoarranque en disco.")

    proc = stream_manager.get_proc(dp)
    if proc and proc.config:
        proc.config["auto_start"] = payload.auto_start
    return {"status": "ok", "auto_start": payload.auto_start}


@router.post("/api/hardware/scan", dependencies=[Depends(verify_api_token)])
async def scan_hardware(restore_ignored: bool = False):
    """Fuerza un sondeo completo de hardware DirectShow (Protegido por Token)."""
    if restore_ignored:
        from core.config_mgr import clear_ignored_devices

        await asyncio.to_thread(clear_ignored_devices)
    await sync_streams_with_hardware()
    return {"status": "ok", "message": "Escaneo de hardware completado"}


@router.get("/api/devices/ignored", dependencies=[Depends(verify_api_token)], response_model=IgnoredDevicesResponse)
async def get_ignored_devices_endpoint():
    """Retorna la lista de dispositivos DirectShow actualmente ignorados/ocultos."""
    from core.config_mgr import get_ignored_devices
    from core.hardware import get_directshow_devices

    raw_ignored = await asyncio.to_thread(get_ignored_devices)
    try:
        cams = await get_directshow_devices()
        connected_cams = {c["device_path"]: (c.get("friendly_name") or c["device_path"]) for c in cams}
    except Exception:
        connected_cams = {}

    items = []
    for entry in raw_ignored:
        dp = entry["device_path"]
        is_conn = dp in connected_cams
        name = entry.get("friendly_name")
        if not name or name == dp:
            name = connected_cams.get(dp, dp)
        items.append(
            IgnoredDeviceItem(
                device_path=dp,
                friendly_name=name,
                is_connected=is_conn,
                ignored_at=entry.get("ignored_at"),
            )
        )
    return IgnoredDevicesResponse(status="ok", ignored_devices=items)


@router.post("/api/devices/unignore", dependencies=[Depends(verify_api_token)])
async def unignore_device_endpoint(payload: DeviceUnignoreRequest):
    """Restaura un dispositivo DirectShow ignorado/eliminado y sincroniza el hardware."""
    from core.config_mgr import unignore_device

    success = await asyncio.to_thread(unignore_device, payload.device_path)
    if not success:
        # Intentar por si payload.device_path vino como ID
        cam = find_camera_by_id_or_path(payload.device_path)
        if cam and "device_path" in cam:
            success = await asyncio.to_thread(unignore_device, cam["device_path"])

    if not success:
        raise HTTPException(
            status_code=404,
            detail="El dispositivo especificado no se encuentra en la lista de ignorados.",
        )

    # Sincronizar inmediatamente con hardware para que reaparezca
    await sync_streams_with_hardware()
    return {"status": "ok", "message": f"Dispositivo {payload.device_path} restaurado exitosamente"}


@router.post("/api/devices/unignore_all", dependencies=[Depends(verify_api_token)])
async def unignore_all_devices_endpoint():
    """Restaura masivamente todos los dispositivos ignorados y sincroniza el hardware."""
    from core.config_mgr import clear_ignored_devices

    await asyncio.to_thread(clear_ignored_devices)
    await sync_streams_with_hardware()
    return {"status": "ok", "message": "Todos los dispositivos ignorados han sido restaurados exitosamente"}


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
    local_ip = get_local_ip()
    from core.mediamtx_mgr import mediamtx_manager
    from core.stream_proc import build_client_urls

    mediamtx_port = mediamtx_manager.get_srt_port()
    cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{port}"
    udp_mode = cfg.get("udp_mode", "multicast")

    urls = build_client_urls(
        protocol=protocol,
        host=local_ip,
        port=port,
        cam_id=cam_id,
        passphrase=passphrase,
        mediamtx_port=mediamtx_port,
        udp_mode=udp_mode,
    )

    return JSONResponse(
        content={
            "status": "ok",
            "device_path": dp,
            "protocol": protocol,
            "udp_mode": udp_mode,
            "connect_url": urls["connect_url"],
            "vlc_url": urls["vlc_url"],
            "has_passphrase": bool(passphrase),
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
