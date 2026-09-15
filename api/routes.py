# ==============================================================================
# RTMS v2.2.3 — Real-Time Multicam System
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
    CameraAutostartToggle, ApplyPresetRequest, ImportConfigRequest,
    FullExportRequest, PreviewTicketRequest
)
from core.ffmpeg_mgr import (
    get_all_stream_statuses, stream_manager, sync_streams_with_hardware,
    build_stream_url
)
from core.config_mgr import (
    update_camera_config, set_camera_autostart, find_camera_by_id_or_path,
    apply_camera_preset, export_config, import_config,
    CAMERA_PRESETS
)
from core.preview_mgr import preview_manager
from core.telemetry import telemetry_service

logger = logging.getLogger("rtms.routes")
router = APIRouter()

_GLOBAL_API_TOKEN: Optional[str] = None
_LAST_IP_CACHE: dict = {"ip": "127.0.0.1", "timestamp": 0.0}

class PreviewTicketManager:
    """
    Gestor en memoria de tickets efímeros para el streaming seguro de previsualizaciones MJPEG (P1-01).
    Evita exponer tokens de sesión de larga duración en URLs de tags <img>.
    """
    def __init__(self, default_ttl: int = 60):
        self._tickets: dict[str, dict] = {}
        self.default_ttl = default_ttl

    def create_ticket(self, device_path: str, ttl: Optional[int] = None) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(32)
        ttl_sec = ttl if (ttl is not None and ttl > 0) else self.default_ttl
        self._tickets[token] = {
            "device_path": device_path,
            "expires_at": time.time() + ttl_sec
        }
        return token

    def validate_ticket(self, ticket: str, device_path: str) -> bool:
        self._cleanup()
        info = self._tickets.get(ticket)
        if not info:
            return False
        if time.time() > info["expires_at"]:
            self._tickets.pop(ticket, None)
            return False

        # Comparar device_path normalizado o resuelto
        cam = find_camera_by_id_or_path(device_path)
        target_dp = cam["device_path"] if cam else device_path
        ticket_dp = info["device_path"]
        ticket_cam = find_camera_by_id_or_path(ticket_dp)
        resolved_ticket_dp = ticket_cam["device_path"] if ticket_cam else ticket_dp
        return target_dp == resolved_ticket_dp

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, v in self._tickets.items() if v["expires_at"] < now]
        for k in expired:
            self._tickets.pop(k, None)

preview_ticket_mgr = PreviewTicketManager()

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
        provided = None
        if isinstance(x_rtms_token, str) and x_rtms_token:
            provided = x_rtms_token
        elif hasattr(request, "headers") and request.headers.get("x-rtms-token"):
            provided = request.headers.get("x-rtms-token")
        elif isinstance(token, str) and token:
            provided = token
        elif hasattr(request, "query_params") and request.query_params.get("token"):
            provided = request.query_params.get("token")

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
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            candidate = s.getsockname()[0]
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
        auto_start=config.auto_start if config.auto_start is not None else True,
        zerolatency=config.zerolatency if config.zerolatency is not None else True,
        is_virtual=config.is_virtual if config.is_virtual is not None else False
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
        proc.config["auto_start"] = config.auto_start
        proc.config["zerolatency"] = config.zerolatency
        proc.config["is_virtual"] = config.is_virtual

        if proc.is_alive:
            await stream_manager.stop_stream(dp)
            await stream_manager.start_stream(dp)

    return {"status": "ok", "message": "Configuración guardada y aplicada"}

@router.delete("/api/stream/{device_path:path}", dependencies=[Depends(verify_api_token)])
async def delete_camera_endpoint(device_path: str):
    """Elimina una cámara de la configuración persistida y detiene su proceso asociado (P1-06)."""
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
        raise HTTPException(status_code=404, detail="Perfil o cámara no encontrados, o error al persistir configuración.")

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
    """Exporta la configuración completa para respaldo o migración (por seguridad, siempre oculta secretos en GET) (P0-05)."""
    return export_config(safe_mode=True)

@router.post("/api/config/export/full", dependencies=[Depends(verify_api_token)])
async def export_full_config_endpoint(payload: FullExportRequest):
    """
    Exporta la configuración completa incluyendo contraseñas sin enmascarar (P0-05).
    Requiere confirmación explícita mediante confirm_export_secrets=True en el cuerpo.
    """
    if not payload.confirm_export_secrets:
        raise HTTPException(
            status_code=400,
            detail="Debe confirmar explícitamente la exportación de secretos con confirm_export_secrets=True."
        )
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

@router.post("/api/preview/ticket", dependencies=[Depends(verify_api_token)])
async def create_preview_ticket(payload: PreviewTicketRequest):
    """Genera un ticket efímero de corta duración para previsualizaciones MJPEG seguras (P1-01)."""
    cam = find_camera_by_id_or_path(payload.device_path)
    dp = cam["device_path"] if cam else payload.device_path
    ttl = payload.ttl_seconds if payload.ttl_seconds is not None else 60
    ticket = preview_ticket_mgr.create_ticket(dp, ttl=ttl)
    return {"ticket": ticket, "expires_in": ttl}

@router.get("/api/stream/{device_path:path}/preview")
async def stream_preview(
    request: Request,
    device_path: str,
    ticket: Optional[str] = None,
    token: Optional[str] = None
):
    """
    Canaliza un stream MJPEG de baja latencia on-demand.
    Soporta autenticación mediante ticket efímero (?ticket=...) o token (?token=... / header).
    Controla concurrencia con semáforo global y slots por cámara (N8, P1-10).
    Al desconectarse el cliente, el generador se detiene inmediatamente liberando recursos al 0%.
    """
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path

    # 1. Autenticación (P1-01)
    if ticket:
        if not preview_ticket_mgr.validate_ticket(ticket, dp):
            raise HTTPException(status_code=403, detail="Ticket de previsualización inválido o expirado.")
    else:
        # Fallback a token de sesión
        await verify_api_token(request, token=token)

    # 2. Verificación de binario FFmpeg (N3)
    if not preview_manager.has_ffmpeg_binary():
        raise HTTPException(status_code=503, detail="Binario de FFmpeg no disponible en el sistema.")

    # 3. Control de concurrencia y ranura de cámara (N8, P1-10)
    slot_acquired = await preview_manager.acquire_slot(dp)
    if not slot_acquired:
        raise HTTPException(
            status_code=429,
            detail="Límite de previsualizaciones concurrentes alcanzado o previsualización ya activa para esta cámara."
        )

    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else (cam or {})

    is_running = proc.is_alive if proc else False
    if is_running:
        protocol = cfg.get("protocol", "srt")
        port = cfg.get("port", 9000)
        passphrase = cfg.get("srt_passphrase", "")
        latency = int(cfg.get("srt_latency", 120))
        zerolatency = bool(cfg.get("zerolatency", True))
        url = build_stream_url(
            protocol=protocol,
            port=port,
            passphrase=passphrase,
            mode="caller",
            latency_ms=latency,
            zerolatency=zerolatency
        )
        gen = preview_manager.generate_mjpeg_stream(url, is_dshow=False, identifier=dp)
    else:
        dshow_target = cfg.get("friendly_name", dp)
        gen = preview_manager.generate_mjpeg_stream(dshow_target, is_dshow=True, identifier=dp)

    async def stream_wrapper():
        try:
            async for chunk in gen:
                yield chunk
        finally:
            await preview_manager.release_slot(dp)

    return StreamingResponse(
        stream_wrapper(),
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
    if not preview_manager.has_ffmpeg_binary():
        raise HTTPException(status_code=503, detail="Binario de FFmpeg no disponible en el sistema.")

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
        latency = int(cfg.get("srt_latency", 120))
        zerolatency = bool(cfg.get("zerolatency", True))
        url = build_stream_url(
            protocol=protocol,
            port=port,
            passphrase=passphrase,
            mode="caller",
            latency_ms=latency,
            zerolatency=zerolatency
        )
        ok = preview_manager.launch_ffplay(url, title=f"RTMS Monitor — {name} ({port})", is_dshow=False)
    else:
        ok = preview_manager.launch_ffplay(name, title=f"RTMS Encuadre DirectShow — {name}", is_dshow=True)

    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo iniciar FFplay. Verifique que bin/ffplay.exe esté disponible.")

    return {"status": "ok", "message": f"Monitor FFplay lanzado para {name}"}
