# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoints de vistas previas en tiempo real, tickets y monitor FFplay.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Rutas REST para generación MJPEG on-demand, tickets efímeros y control de monitorización."""

import asyncio
import logging
import secrets
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from api.deps import get_global_api_token, preview_ticket_mgr, verify_api_token
from api.schemas import PreviewTicketRequest
from core.config_mgr import find_camera_by_id_or_path
from core.mediamtx_mgr import clean_camera_id, mediamtx_manager
from core.preview_mgr import preview_manager
from core.stream_manager import stream_manager
from core.stream_proc import build_stream_url

logger = logging.getLogger("rtms.api.preview")
router = APIRouter()


@router.post("/api/preview/ticket", dependencies=[Depends(verify_api_token)])
@router.post("/api/stream/{device_path:path}/preview_ticket", dependencies=[Depends(verify_api_token)])
async def create_preview_ticket(payload: Optional[PreviewTicketRequest] = None, device_path: Optional[str] = None):
    """Genera un ticket efímero de corta duración para previsualizaciones MJPEG seguras."""
    target_path = device_path or (payload.device_path if payload else None)
    if not target_path:
        raise HTTPException(status_code=400, detail="device_path es requerido.")
    cam = find_camera_by_id_or_path(target_path)
    dp = cam["device_path"] if cam else target_path
    ttl = payload.ttl_seconds if (payload and payload.ttl_seconds is not None) else 60
    ticket = preview_ticket_mgr.create_ticket(dp, ttl=ttl)
    return {"ticket": ticket, "expires_in": ttl}


@router.get("/api/stream/{device_path:path}/preview")
async def stream_preview(request: Request, device_path: str, ticket: Optional[str] = None):
    """
    Canaliza un stream MJPEG de baja latencia on-demand.
    Soporta autenticación mediante ticket efímero de consumo único (?ticket=...) o cabecera X-RTMS-Token.
    Controla concurrencia con semáforo global y slots por cámara.
    Al desconectarse el cliente, el generador se detiene inmediatamente liberando recursos al 0%.
    """
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path

    # 1. Autenticación segura (ticket efímero o token en cabecera)
    if ticket:
        if not preview_ticket_mgr.consume_ticket(ticket, dp):
            raise HTTPException(status_code=403, detail="Ticket de previsualización inválido, expirado o ya consumido.")
    else:
        # En producción se rechaza el token global por query string
        if request.query_params.get("token"):
            raise HTTPException(
                status_code=403,
                detail="El uso de token global por query parameter está deshabilitado por seguridad. Utilice tickets efímeros o la cabecera X-RTMS-Token.",
            )
        await verify_api_token(request)

    # 2. Verificación de binario FFmpeg
    if not preview_manager.has_ffmpeg_binary():
        raise HTTPException(status_code=503, detail="Binario de FFmpeg no disponible en el sistema.")

    # 3. Control de concurrencia y ranura por cámara
    slot_acquired = await preview_manager.acquire_slot(dp)
    if not slot_acquired:
        raise HTTPException(
            status_code=429,
            detail="Límite de previsualizaciones concurrentes alcanzado o previsualización ya activa para esta cámara.",
        )

    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else (cam or {})

    raw_device = cfg.get("device_path", cfg.get("friendly_name", dp))
    is_virtual = bool(
        str(raw_device).startswith("virtual://")
        or str(raw_device).startswith("testsrc")
        or cfg.get("is_virtual_generator", False)
        or cfg.get("is_virtual", False)
    )

    is_running = proc.is_alive if proc else False
    if is_running:
        protocol = cfg.get("protocol", "srt")
        from core.secrets_mgr import unprotect_secret

        raw_pass = cfg.get("srt_passphrase", "")
        passphrase = unprotect_secret(raw_pass) if raw_pass else ""
        latency = int(cfg.get("srt_latency", 120))
        zerolatency = bool(cfg.get("zerolatency", True))

        if protocol == "srt":
            from core.mediamtx_mgr import clean_camera_id, mediamtx_manager

            mediamtx_port = mediamtx_manager.get_srt_port()
            cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{cfg.get('port', 9000)}"
            clean_cam_id = clean_camera_id(cam_id)
            url = build_stream_url(
                protocol="srt",
                port=mediamtx_port,
                passphrase=passphrase,
                mode="caller",
                latency_ms=latency,
                zerolatency=zerolatency,
                streamid=f"read:{clean_cam_id}",
            )
        else:
            port = cfg.get("port", 9000)
            udp_mode = cfg.get("udp_mode", "multicast")
            udp_host = cfg.get("udp_host", "127.0.0.1")
            url = build_stream_url(
                protocol=protocol,
                port=port,
                passphrase=passphrase,
                mode="caller",
                latency_ms=latency,
                zerolatency=zerolatency,
                udp_mode=udp_mode,
                udp_host=udp_host,
            )
        gen = preview_manager.generate_mjpeg_stream(url, is_dshow=False, is_virtual=False, identifier=dp)
    else:
        if is_virtual:
            gen = preview_manager.generate_mjpeg_stream("virtual", is_dshow=False, is_virtual=True, identifier=dp)
        else:
            dshow_target = cfg.get("friendly_name", dp)
            gen = preview_manager.generate_mjpeg_stream(dshow_target, is_dshow=True, is_virtual=False, identifier=dp)

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
        },
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

    raw_device = cfg.get("device_path", cfg.get("friendly_name", dp))
    is_virtual = bool(
        str(raw_device).startswith("virtual://")
        or str(raw_device).startswith("testsrc")
        or cfg.get("is_virtual_generator", False)
        or cfg.get("is_virtual", False)
    )

    target = "virtual://testsrc2" if is_virtual else cfg.get("friendly_name", dp)
    jpeg_bytes = await preview_manager.get_snapshot_frame(target)
    if not jpeg_bytes:
        raise HTTPException(status_code=503, detail="No se pudo capturar cuadro de previsualización")

    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.post("/api/stream/{device_path:path}/ffplay", dependencies=[Depends(verify_api_token)])
async def launch_external_ffplay(device_path: str):
    """Lanza ventana nativa de ultra baja latencia con FFplay para monitorización dedicada."""
    cam = find_camera_by_id_or_path(device_path)
    if not cam:
        raise HTTPException(status_code=404, detail="Dispositivo de cámara no encontrado")

    dp = cam["device_path"]
    proc = stream_manager.get_proc(dp)
    cfg = proc.config if (proc and proc.config) else cam

    name = cfg.get("friendly_name", dp)
    raw_device = cfg.get("device_path", name)
    is_virtual = bool(
        str(raw_device).startswith("virtual://")
        or str(raw_device).startswith("testsrc")
        or cfg.get("is_virtual_generator", False)
        or cfg.get("is_virtual", False)
    )
    is_running = proc.is_alive if proc else False

    if is_running:
        protocol = cfg.get("protocol", "srt")
        from core.secrets_mgr import unprotect_secret

        raw_pass = cfg.get("srt_passphrase", "")
        passphrase = unprotect_secret(raw_pass) if raw_pass else ""
        latency = int(cfg.get("srt_latency", 120))
        zerolatency = bool(cfg.get("zerolatency", True))

        if protocol == "srt":
            from core.mediamtx_mgr import clean_camera_id, mediamtx_manager

            mediamtx_port = mediamtx_manager.get_srt_port()
            cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{cfg.get('port', 9000)}"
            clean_cam_id = clean_camera_id(cam_id)
            url = build_stream_url(
                protocol="srt",
                port=mediamtx_port,
                passphrase=passphrase,
                mode="caller",
                latency_ms=latency,
                zerolatency=zerolatency,
                streamid=f"read:{clean_cam_id}",
            )
            title = f"RTMS Monitor — {name} (SRT :{mediamtx_port})"
        else:
            port = cfg.get("port", 9000)
            udp_mode = cfg.get("udp_mode", "multicast")
            udp_host = cfg.get("udp_host", "127.0.0.1")
            url = build_stream_url(
                protocol=protocol,
                port=port,
                passphrase=passphrase,
                mode="caller",
                latency_ms=latency,
                zerolatency=zerolatency,
                udp_mode=udp_mode,
                udp_host=udp_host,
            )
            title = f"RTMS Monitor — {name} (UDP :{port})"
        ok = preview_manager.launch_ffplay(url, title=title, is_dshow=False, is_virtual=False)
    else:
        if is_virtual:
            ok = preview_manager.launch_ffplay(
                "virtual", title=f"RTMS Generador Virtual — {name}", is_dshow=False, is_virtual=True
            )
        else:
            ok = preview_manager.launch_ffplay(
                name, title=f"RTMS Encuadre DirectShow — {name}", is_dshow=True, is_virtual=False
            )

    if not ok:
        raise HTTPException(
            status_code=500, detail="No se pudo iniciar FFplay. Verifique que bin/ffplay.exe esté disponible."
        )

    return {"status": "ok", "message": f"Monitor FFplay lanzado para {name}"}


@router.post("/api/stream/{device_path:path}/whep")
@router.post("/api/whep/{device_path:path}")
async def whep_proxy_endpoint(request: Request, device_path: str, ticket: Optional[str] = None):
    """
    Endpoint proxy para señalización WebRTC WHEP (RFC 9397) con MediaMTX.
    Recibe la oferta SDP del cliente y retorna la respuesta SDP del Media Server.
    Elimina problemas de CORS y centraliza la autenticación segura por token o ticket.
    """
    cam = find_camera_by_id_or_path(device_path)
    dp = cam["device_path"] if cam else device_path
    cam_id = cam.get("id", dp) if cam else dp
    clean_cam_id = clean_camera_id(cam_id)

    # 1. Autenticación (ticket efímero, token por query string o cabecera X-RTMS-Token)
    if ticket:
        if not preview_ticket_mgr.consume_ticket(ticket, dp):
            raise HTTPException(status_code=403, detail="Ticket de previsualización inválido o expirado.")
    else:
        token_q = request.query_params.get("token")
        if token_q:
            expected = getattr(request.app.state, "api_token", get_global_api_token())
            if not expected or not secrets.compare_digest(str(token_q), str(expected)):
                raise HTTPException(status_code=403, detail="Token inválido.")
        else:
            await verify_api_token(request)

    # 2. Lectura del cuerpo SDP de la oferta
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Cuerpo SDP de oferta vacío.")

    webrtc_port = mediamtx_manager.get_webrtc_port()
    whep_url = f"http://127.0.0.1:{webrtc_port}/{clean_cam_id}/whep"

    def _forward_sdp():
        req = urllib.request.Request(
            whep_url,
            data=body_bytes,
            headers={"Content-Type": "application/sdp"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                status = resp.status
                data = resp.read().decode("utf-8", errors="replace")
                return status, data
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            return he.code, err_body
        except Exception as ex:
            return 502, str(ex)

    status_code, answer_sdp = await asyncio.to_thread(_forward_sdp)
    if status_code in (200, 201):
        return Response(
            content=answer_sdp,
            status_code=status_code,
            media_type="application/sdp",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    raise HTTPException(
        status_code=status_code,
        detail=f"Fallo en señalización WHEP con MediaMTX: {answer_sdp}",
    )
