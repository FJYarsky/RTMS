# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.3
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import socket
import psutil
import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import List, Dict, Any, Optional

from .schemas import CameraConfigUpdate, StreamAction, AutostartToggle, CameraAutostartToggle
from core.ffmpeg_mgr import get_all_stream_statuses, stream_manager, sync_streams_with_hardware
from core.config_mgr import update_camera_config, set_camera_autostart

logger = logging.getLogger("rtms.routes")
router = APIRouter()

_GLOBAL_API_TOKEN: Optional[str] = None

def set_global_api_token(token: str):
    """Establece el token de sesión criptográfico generado al inicio de la aplicación."""
    global _GLOBAL_API_TOKEN
    _GLOBAL_API_TOKEN = token

async def verify_api_token(x_rtms_token: Optional[str] = Header(None, alias="X-RTMS-Token")):
    """
    Middleware de seguridad que valida el token de sesión en todas las peticiones mutantes (POST).
    Previene de forma definitiva ataques de tipo Localhost CSRF / Drive-by desde navegadores web.
    """
    if _GLOBAL_API_TOKEN is not None:
        if not x_rtms_token or x_rtms_token != _GLOBAL_API_TOKEN:
            logger.warning("Petición rechazada: Token de seguridad X-RTMS-Token inválido o ausente.")
            raise HTTPException(status_code=403, detail="Acceso denegado: Token de seguridad inválido o ausente.")

def get_local_ip() -> str:
    """Obtiene la IP local de la máquina en la LAN (online y offline)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        addrs = psutil.net_if_addrs()
        for iface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ip_candidate = addr.address
                    if not ip_candidate.startswith("127.") and not ip_candidate.startswith("169.254."):
                        return ip_candidate
    except Exception:
        pass

    return "127.0.0.1"

@router.get("/api/status")
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
        "version": "2.0.3",
        "local_ip": get_local_ip(),
        "autostart_enabled": is_autostart_enabled(),
        "streams": sanitized_streams
    }

@router.get("/api/system/metrics")
async def get_system_metrics():
    """Retorna métricas de hardware (CPU, RAM) y telemetría de streams en vivo para el HUD."""
    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    
    statuses = get_all_stream_statuses()
    running_streams = [s for s in statuses if s["status"]["state"] == "running"]
    total_bitrate = sum(s["status"]["current_bitrate_kbps"] for s in running_streams)

    return {
        "cpu_percent": cpu_pct,
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / (1024 * 1024), 1),
        "memory_total_mb": round(mem.total / (1024 * 1024), 1),
        "active_streams_count": len(running_streams),
        "total_bitrate_kbps": round(total_bitrate, 1)
    }

@router.post("/api/system/emergency_stop", dependencies=[Depends(verify_api_token)])
async def emergency_stop():
    """Detiene inmediatamente todos los flujos de FFmpeg de forma segura (Protegido por Token)."""
    await stream_manager.emergency_stop_all()
    return {"status": "ok", "message": "Todas las transmisiones fueron detenidas de emergencia."}

@router.post("/api/stream/action", dependencies=[Depends(verify_api_token)])
async def handle_stream_action(action: StreamAction):
    """Inicia, detiene o reinicia un flujo manualmente (Protegido por Token)."""
    dp = action.device_path
    
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
    # Si la contraseña enviada es la enmascarada "••••••••", preservar la existente
    passphrase_to_set = config.srt_passphrase
    proc = stream_manager.get_proc(config.device_path)
    if passphrase_to_set == "••••••••" and proc and proc.config:
        passphrase_to_set = proc.config.get("srt_passphrase", "")

    update_camera_config(
        device_path=config.device_path, 
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
        
        if proc.state == "running":
            await stream_manager.stop_stream(config.device_path)
            await stream_manager.start_stream(config.device_path)
            
    return {"status": "ok", "message": "Configuración guardada y aplicada"}

@router.post("/api/stream/autostart_toggle", dependencies=[Depends(verify_api_token)])
async def toggle_cam_autostart(payload: CameraAutostartToggle):
    """Activa o desactiva el autoarranque desatendido de una cámara individual (Protegido por Token)."""
    set_camera_autostart(payload.device_path, payload.auto_start)
    proc = stream_manager.get_proc(payload.device_path)
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

@router.get("/api/stream/logs")
async def get_stream_logs(device_path: str):
    """Retorna los logs de FFmpeg del flujo solicitado."""
    proc = stream_manager.get_proc(device_path)
    if not proc:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"logs": proc.get_logs()}

@router.post("/api/power/apply", dependencies=[Depends(verify_api_token)])
async def apply_power():
    """Aplica las optimizaciones de energía y estabilidad en Windows (Protegido por Token)."""
    from core.system_env import setup_windows_environment
    setup_windows_environment()
    return {"status": "ok", "message": "Optimizaciones de estabilidad aplicadas"}

@router.post("/api/power/restore", dependencies=[Depends(verify_api_token)])
async def restore_power():
    """Restaura la configuración original de energía de Windows (Protegido por Token)."""
    from core.system_env import restore_original_power_settings
    result = restore_original_power_settings()
    if result.get("status") == "ok":
        return result
    raise HTTPException(status_code=400, detail=result.get("message", "Error al restaurar"))

@router.get("/api/power/status")
async def power_status():
    import os
    from core.system_env import BACKUP_FILE
    return {"optimizations_applied": os.path.exists(BACKUP_FILE)}
