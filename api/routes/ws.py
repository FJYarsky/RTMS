# ==============================================================================
# RTMS — Real-Time Multicam System
# Endpoint WebSocket para telemetría en tiempo real y eventos de hardware.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Ruta WebSocket /ws/telemetry con soporte de token y distribución a 10 Hz."""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.deps import _GLOBAL_API_TOKEN
from core.telemetry_hub import telemetry_hub

logger = logging.getLogger("rtms.api.ws")
router = APIRouter()


@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Canal bidireccional WebSocket para telemetría ultra-reactiva a 10 Hz y eventos de estado.
    Valida el token de sesión (vía query param, cookie o cabecera) antes de aceptar la conexión.
    """
    expected_token = getattr(websocket.app.state, "api_token", _GLOBAL_API_TOKEN)
    if expected_token is not None:
        if token is not None:
            logger.warning("Conexión WebSocket rechazada: Token en query string prohibido por directiva de seguridad.")
            await websocket.close(code=1008, reason="Query token forbidden")
            return
        provided = websocket.headers.get("x-rtms-token") or websocket.cookies.get("rtms_session")
        if not provided or not secrets.compare_digest(str(provided), str(expected_token)):
            logger.warning("Conexión WebSocket rechazada: Token inválido o ausente.")
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()
    await telemetry_hub.register(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.debug("Cliente WebSocket desconectado normalmente.")
    except Exception as e:
        logger.debug(f"Excepción en conexión WebSocket de telemetría: {e}")
    finally:
        await telemetry_hub.unregister(websocket)
