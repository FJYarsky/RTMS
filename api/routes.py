# ==============================================================================
# RTMS v2.2.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import socket
import psutil
import logging
import secrets
import time
from fastapi import APIRouter, HTTPException, Header, Depends, Request, Response
from fastapi.responses import StreamingResponse
from typing import Optional

from core.__version__ import __version__
from .schemas import (
    CameraConfigUpdate, StreamAction, AutostartToggle,
    CameraAutostartToggle, ApplyPresetRequest, ImportConfigRequest
)
from core.ffmpeg_mgr import get_all_stream_statuses, stream_manager, sync_streams_with_hardware
from core.config_mgr import (
    update_camera_config, set_camera_autostart, find_camera_by_id_or_path,
    apply_camera_preset, export_config, import_config, CAMERA_PRESETS
)
from core.preview_mgr import preview_manager
from core.telemetry import telemetry_service

logger = logging.getLogger("rtms.routes")
router = APIRouter()

_GLOBAL_API_TOKEN: Optional[str] = None
_LAST_IP_CACHE: dict = {"ip": "127.0.0.1", "timestamp": 0.0}

def set_global_api_token(token: str):
    """Establece el token de sesión criptográfico generado al inicio de la aplicación."""
    global _GLOBAL_API_TOKEN
    _GLOBAL_API_TOKEN = token

async def verify_api_token(
    request: Request,
    x_rtms_token: Optional[str] = Header(None, alias="X-RTMS-Token"),
    token: Optional[str] = None
):
    """
    Middleware de seguridad que valida el token de sesión en peticiones protegidas.
    Soporta Header 'X-RTMS-Token' y query param '?token=' (para tags <img> de preview).
    Utiliza comparación en tiempo constante para mitigar timing attacks.
    """
    expected_token = getattr(request.app.state, "api_token", _GLOBAL_API_TOKEN)
    if expected_token is not None:
        provided = x_rtms_token or token
        if not provided or not secrets.compare_digest(str(provided), str(expected_token)):
            logger.warning("Petición rechazada: Token de seguridad X-RTMS-Token inválido o ausente.")
            raise HTTPException(status_code=403, detail="Acceso denegado: Token de seguridad inválido o ausente.")

def get_local_ip() -> str:
    """Obtiene la IP local con caché TTL de 30s para evitar sondeos de sockets constantes."""
    global _LAST_IP_CACHE
    now = time.time()
    if now - _LAST_IP_CACHE["timestamp"] < 30.0:
        return _LAST_IP_CACHE["ip"]

    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        candidate = s.getsockname()[0]
        s.close()
        if candidate and not candidate.startswith("127."):
            ip = candidate
    except Exception:
        try:
            addrs = psutil.net_if_addrs()
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        ip_candidate = addr.address
                        if not ip_candidate.startswith("127.") and not ip_candidate.startswith("169.254."):
                            ip = ip_candidate
                            break
                if ip != "127.0.0.1":
                    break
        except Exception:
            pass

    _LAST_IP_CACHE = {"ip": ip, "timestamp": now}
    return ip

@router.get("/healthz")
async def healthz():
    """Endpoint público de verificación de salud para supervisores externos de procesos."""
    return {"status": "ok", "version": __version__}

@router.get("/api/status", dependencies=[Depends(verify_api_token)])
async def get_status():
    """Retorna el estado general del sistema, IP local y flujos con contraseñas enmascaradas."""
    from core.autostart import is_autostart_enabled
    raw_streams = get_all_stream_statuses()

    # Seguridad: Enmascarar srt_passphrase para no exponerla en texto plano
    sanitized_streams = []
    for s in raw_streams:
        sc = dict(s)
        real_pass = sc.get("srt_passphrase", "")
        sc["has_passphrase"] = bool(real_pass)
        sc["srt_passphrase"] = "••••••••" if real_pass else ""
        sanitized_streams.append(sc)

    return {
        "version": __version__,
        "local_ip": get_local_ip(),
        "autostart_enabled": is_autostart_enabled(),
        "streams": sanitized_streams,
        "presets": {k: v["name"] for k, v in CAMERA_PRESETS.items()}
    }

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
async def emergency_stop():
    """Detiene inmediatamente todos los flujos de FFmpeg de forma segura (Protegido por Token)."""
    await stream_manager.emergency_stop_all()
    return {"status": "ok", "message": "Todas las transmisiones fueron detenidas de emergencia."}

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
    if passphrase_to_set == "••••••••" and proc and proc.config:
        passphrase_to_set = proc.config.get("srt_passphrase", "")

    update_camera_config(
        device_path=dp,
        resolution=config.resolution,
        fps=config.fps,
        bitrate=config.bitrate,
        protocol=config.protocol or "srt",
        encoder=config.encoder or "auto",
        srt_latency=config.srt_latency or 120,
        srt_passphrase=passphrase_to_set or "",
        auto_start=config.auto_start if config.auto_start is not None else True,
        zerolatency=config.zerolatency if config.zerolatency is not None else True,
        is_virtual=config.is_virtual if config.is_virtual is not None else False
    )

    if proc:
        proc.config["resolution"] = config.resolution
        proc.config["fps"] = config.fps
        proc.config["bitrate"] = config.bitrate
        proc.config["protocol"] = config.protocol or "srt"
        proc.config["encoder"] = config.encoder or "auto"
        proc.config["srt_latency"] = config.srt_latency or 120
        proc.config["srt_passphrase"] = passphrase_to_set or ""
        proc.config["auto_start"] = config.auto_start
        proc.config["zerolatency"] = config.zerolatency
        proc.config["is_virtual"] = config.is_virtual

        if proc.is_alive:
            await stream_manager.stop_stream(dp)
            await stream_manager.start_stream(dp)

    return {"status": "ok", "message": "Configuración guardada y aplicada"}

@router.post("/api/stream/preset", dependencies=[Depends(verify_api_token)])
async def apply_preset_endpoint(payload: ApplyPresetRequest):
    """Aplica un perfil predefinido a una cámara existente."""
    cam = find_camera_by_id_or_path(payload.device_path)
    dp = cam["device_path"] if cam else payload.device_path

    updated_cam = apply_camera_preset(dp, payload.preset_key)
    if not updated_cam:
        raise HTTPException(status_code=404, detail="Perfil o cámara no encontrados")

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

    set_camera_autostart(dp, payload.auto_start)
    proc = stream_manager.get_proc(dp)
    if proc and proc.config:
        proc.config["auto_start"] = payload.auto_start
    return {"status": "ok", "auto_start": payload.auto_start}

@router.post("/api/hardware/scan", dependencies=[Depends(verify_api_token)])
async def scan_hardware():
    """Fuerza un sondeo completo de hardware DirectShow (Protegido por Token)."""
    await sync_streams_with_hardware()
    return {"status": "ok", "message": "Escaneo de hardware completado"}

@router.post("/api/autostart", dependencies=[Depends(verify_api_token)])
async def set_autostart(toggle: AutostartToggle):
    """Habilita o deshabilita el autoarranque de RTMS con Windows (Protegido por Token)."""
    from core.autostart import enable_autostart
    enable_autostart(toggle.enable)
    return {"status": "ok", "autostart": toggle.enable}

@router.get("/api/stream/logs", dependencies=[Depends(verify_api_token)])
async def get_stream_logs(device_path: str):
    """Retorna los logs sanitizados de FFmpeg del flujo solicitado (Protegido por Token)."""
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path

    proc = stream_manager.get_proc(dp)
    if not proc:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"logs": proc.get_logs()}

@router.post("/api/power/apply", dependencies=[Depends(verify_api_token)])
async def apply_power():
    """Aplica las optimizaciones de energía y estabilidad en Windows y reporta el resultado real."""
    from core.system_env import setup_windows_environment
    result = setup_windows_environment()
    return result

@router.post("/api/power/restore", dependencies=[Depends(verify_api_token)])
async def restore_power():
    """Restaura la configuración original de energía de Windows (Protegido por Token)."""
    from core.system_env import restore_original_power_settings
    result = restore_original_power_settings()
    if result.get("status") == "ok":
        return result
    raise HTTPException(status_code=400, detail=result.get("message", "Error al restaurar"))

@router.get("/api/power/status", dependencies=[Depends(verify_api_token)])
async def power_status():
    """Retorna si las optimizaciones de energía están aplicadas actualmente."""
    import os
    from core.system_env import BACKUP_FILE
    return {"optimizations_applied": os.path.exists(BACKUP_FILE)}

@router.get("/api/config/export", dependencies=[Depends(verify_api_token)])
async def export_config_endpoint(safe_mode: bool = True):
    """Exporta la configuración completa para respaldo o migración (safe_mode oculta secretos por defecto)."""
    return export_config(safe_mode=safe_mode)

@router.post("/api/config/import", dependencies=[Depends(verify_api_token)])
async def import_config_endpoint(payload: ImportConfigRequest):
    """Importa una configuración externa completa previa validación de esquema."""
    success = import_config(payload.config_data)
    if not success:
        raise HTTPException(status_code=400, detail="Estructura de configuración inválida")
    await sync_streams_with_hardware()
    return {"status": "ok", "message": "Configuración importada y aplicada exitosamente"}

@router.get("/api/stream/{device_path:path}/preview", dependencies=[Depends(verify_api_token)])
async def stream_preview(device_path: str):
    """
    Canaliza un stream MJPEG de baja latencia on-demand.
    Si la cámara está emitiendo, lee localmente del flujo SRT/UDP sin tocar DirectShow.
    Si la cámara está detenida, toma captura DirectShow para encuadre.
    Al desconectarse el cliente, el generador se detiene inmediatamente liberando recursos al 0%.
    """
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path
    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else (cam or {})

    is_running = proc.is_alive if proc else False
    if is_running:
        protocol = cfg.get("protocol", "srt")
        port = cfg.get("port", 9000)
        passphrase = cfg.get("srt_passphrase", "")
        if protocol == "srt":
            url = f"srt://127.0.0.1:{port}?mode=caller"
            if passphrase:
                url += f"&passphrase={passphrase}"
        else:
            url = f"udp://127.0.0.1:{port}"
        gen = preview_manager.generate_mjpeg_stream(url, is_dshow=False)
    else:
        dshow_target = cfg.get("friendly_name", dp)
        gen = preview_manager.generate_mjpeg_stream(dshow_target, is_dshow=True)

    return StreamingResponse(
        gen,
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

@router.get("/api/stream/{device_path:path}/preview_frame", dependencies=[Depends(verify_api_token)])
async def stream_preview_frame(device_path: str):
    """Retorna un único frame JPEG para vista estática de encuadre."""
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path
    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else (cam or {})

    target = cfg.get("friendly_name", dp)
    jpeg_bytes = await preview_manager.get_snapshot_frame(target)
    if not jpeg_bytes:
        raise HTTPException(status_code=503, detail="No se pudo capturar cuadro de previsualización")

    return Response(content=jpeg_bytes, media_type="image/jpeg")

@router.post("/api/stream/{device_path:path}/ffplay", dependencies=[Depends(verify_api_token)])
async def launch_external_ffplay(device_path: str):
    """Lanza ventana nativa de ultra baja latencia con FFplay para monitorización dedicada."""
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path
    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else (cam or {})

    name = cfg.get("friendly_name", dp)
    is_running = proc.is_alive if proc else False

    if is_running:
        protocol = cfg.get("protocol", "srt")
        port = cfg.get("port", 9000)
        passphrase = cfg.get("srt_passphrase", "")
        if protocol == "srt":
            url = f"srt://127.0.0.1:{port}?mode=caller"
            if passphrase:
                url += f"&passphrase={passphrase}"
        else:
            url = f"udp://127.0.0.1:{port}"
        ok = preview_manager.launch_ffplay(url, title=f"RTMS Monitor — {name} ({port})", is_dshow=False)
    else:
        ok = preview_manager.launch_ffplay(name, title=f"RTMS Encuadre DirectShow — {name}", is_dshow=True)

    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo iniciar FFplay. Verifique que bin/ffplay.exe esté disponible.")

    return {"status": "ok", "message": f"Monitor FFplay lanzado para {name}"}
