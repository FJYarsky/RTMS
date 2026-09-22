# ==============================================================================
# RTMS — Real-Time Multicam System
# Dependencias comunes, autenticación y gestión de tickets de seguridad.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Dependencias compartidas de FastAPI, tokens de sesión y gestor de tickets efímeros."""

import logging
import secrets
import socket
import threading
import time
from typing import Optional

from fastapi import Header, HTTPException, Request

from core.config_mgr import find_camera_by_id_or_path

logger = logging.getLogger("rtms.api.deps")

_GLOBAL_API_TOKEN: Optional[str] = None
_LAST_IP_CACHE: dict = {"ip": "127.0.0.1", "timestamp": 0.0}


class PreviewTicketManager:
    """
    Gestor en memoria de tickets efímeros para el streaming seguro de previsualizaciones MJPEG.
    Implementa consumo atómico de un solo uso (single-use), protección contra condiciones
    de carrera mediante threading.Lock() y límite superior de tickets en memoria.
    """

    MAX_TICKETS = 100

    def __init__(self, default_ttl: int = 60):
        self._tickets: dict[str, dict] = {}
        self.default_ttl = default_ttl
        self._lock = threading.Lock()

    def create_ticket(self, device_path: str, ttl: Optional[int] = None) -> str:
        with self._lock:
            self._cleanup_locked()
            if len(self._tickets) >= self.MAX_TICKETS:
                oldest = min(self._tickets.keys(), key=lambda k: self._tickets[k]["expires_at"])
                self._tickets.pop(oldest, None)

            token = secrets.token_urlsafe(32)
            ttl_sec = ttl if (ttl is not None and ttl > 0) else self.default_ttl
            self._tickets[token] = {"device_path": device_path, "expires_at": time.time() + ttl_sec}
            return token

    def consume_ticket(self, ticket: str, device_path: str) -> bool:
        """
        Valida y elimina atómicamente el ticket tras su primer uso exitoso (single-use).
        Retorna True si era válido y correspondía a la cámara indicada; False en caso contrario.
        """
        with self._lock:
            self._cleanup_locked()
            info = self._tickets.pop(ticket, None)
            if not info:
                return False
            if time.time() > info["expires_at"]:
                return False

            cam = find_camera_by_id_or_path(device_path)
            target_dp = cam["device_path"] if cam else device_path
            ticket_dp = info["device_path"]
            ticket_cam = find_camera_by_id_or_path(ticket_dp)
            resolved_ticket_dp = ticket_cam["device_path"] if ticket_cam else ticket_dp
            return target_dp == resolved_ticket_dp

    def validate_ticket(self, ticket: str, device_path: str) -> bool:
        """Valida si el ticket existe y está vigente sin consumirlo."""
        with self._lock:
            self._cleanup_locked()
            info = self._tickets.get(ticket)
            if not info:
                return False
            if time.time() > info["expires_at"]:
                self._tickets.pop(ticket, None)
                return False

            cam = find_camera_by_id_or_path(device_path)
            target_dp = cam["device_path"] if cam else device_path
            ticket_dp = info["device_path"]
            ticket_cam = find_camera_by_id_or_path(ticket_dp)
            resolved_ticket_dp = ticket_cam["device_path"] if ticket_cam else ticket_dp
            return target_dp == resolved_ticket_dp

    def invalidate_for_device(self, device_path: str) -> None:
        """Invalida de inmediato todos los tickets asociados a un dispositivo."""
        with self._lock:
            cam = find_camera_by_id_or_path(device_path)
            target_dp = cam["device_path"] if cam else device_path
            to_remove = []
            for k, v in self._tickets.items():
                t_cam = find_camera_by_id_or_path(v["device_path"])
                res_dp = t_cam["device_path"] if t_cam else v["device_path"]
                if res_dp == target_dp:
                    to_remove.append(k)
            for k in to_remove:
                self._tickets.pop(k, None)

    def _cleanup_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._tickets.items() if v["expires_at"] < now]
        for k in expired:
            self._tickets.pop(k, None)

    def _cleanup(self) -> None:
        with self._lock:
            self._cleanup_locked()


preview_ticket_mgr = PreviewTicketManager()


def set_global_api_token(token: str):
    """Establece el token de sesión criptográfico generado al inicio de la aplicación."""
    global _GLOBAL_API_TOKEN
    _GLOBAL_API_TOKEN = token


async def verify_api_token(
    request: Request,
    x_rtms_token: Optional[str] = Header(None, alias="X-RTMS-Token"),
):
    """
    Middleware de seguridad que valida el token de sesión en peticiones protegidas.
    Exige la cabecera 'X-RTMS-Token' o cookie HttpOnly 'rtms_session'.
    Rechaza tajantemente peticiones con token en query params con HTTP 403 Forbidden.
    Utiliza comparación en tiempo constante para mitigar timing attacks.
    """
    if "token" in request.query_params:
        logger.warning(
            f"Rechazando petición con token en query param desde {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(status_code=403, detail="Acceso denegado: Token en query string prohibido por seguridad.")

    expected_token = getattr(request.app.state, "api_token", _GLOBAL_API_TOKEN)
    if expected_token is not None:
        provided = None
        if isinstance(x_rtms_token, str) and x_rtms_token:
            provided = x_rtms_token
        elif hasattr(request, "headers") and request.headers.get("x-rtms-token"):
            provided = request.headers.get("x-rtms-token")
        elif hasattr(request, "cookies") and request.cookies.get("rtms_session"):
            provided = request.cookies.get("rtms_session")

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
            ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"

    _LAST_IP_CACHE = {"ip": ip, "timestamp": now}
    return ip
