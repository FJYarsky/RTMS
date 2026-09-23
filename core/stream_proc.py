# ==============================================================================
# RTMS — Real-Time Multicam System
# Definición de procesos y máquinas de estados para flujos de transmisión.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Máquina de estados, categorías de error y proceso de streaming individual."""

import asyncio
import logging
import re
import sys
import urllib.parse
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.sanitizer import sanitize_log_line

logger = logging.getLogger("rtms.stream_proc")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW


class ErrorCategory(str, Enum):
    """Taxonomía formal de categorías de error para diagnósticos y políticas de reconexión."""

    CONFIGURATION = "configuration"
    DEVICE = "device"
    ENCODER = "encoder"
    NETWORK = "network"
    PORT_COLLISION = "port_collision"
    PROCESS = "process"
    AUTHENTICATION = "authentication"
    UNKNOWN = "unknown"


class State(str, Enum):
    """Estados del ciclo de vida de un flujo de transmisión."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    RESTARTING = "restarting"
    RECOVERING = "recovering"
    STOPPING = "stopping"
    DISCONNECTED = "disconnected"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


def build_multicast_url(port: int) -> str:
    """Calcula y retorna la URL multicast UDP para el puerto indicado con buffer optimizado (4MB)."""
    ip_last_octet = (int(port) % 200) + 1
    return f"udp://239.255.0.{ip_last_octet}:{port}?pkt_size=1316&buffer_size=4194304&overrun_nonfatal=1&fifo_size=50000000"


def build_unicast_url(port: int, host: str = "127.0.0.1") -> str:
    """Calcula y retorna la URL unicast UDP local/remota con buffer optimizado (4MB)."""
    clean_host = host.strip() or "127.0.0.1"
    return f"udp://{clean_host}:{port}?pkt_size=1316&buffer_size=4194304&overrun_nonfatal=1&fifo_size=50000000"


def build_stream_url(
    protocol: str,
    port: int,
    passphrase: str = "",
    mode: str = "listener",
    latency_ms: int = 120,
    zerolatency: bool = True,
    streamid: Optional[str] = None,
    udp_mode: str = "multicast",
    udp_host: str = "127.0.0.1",
) -> str:
    """Construye la URL normalizada de transmisión para SRT o UDP con parámetros optimizados de baja latencia."""
    if protocol == "udp_unicast" or (protocol == "udp" and udp_mode == "unicast"):
        return build_unicast_url(port, host=udp_host)
    if protocol == "udp":
        return build_multicast_url(port)

    # Protocolo SRT
    latency_us = int(latency_ms) * 1000
    host = "0.0.0.0" if mode == "listener" else "127.0.0.1"
    drop_flag = "1" if zerolatency else "0"
    params = {
        "mode": mode,
        "latency": str(latency_us),
        "transtype": "live",
        "tlpktdrop": drop_flag,
        "sndbuf": "262144",
        "rcvbuf": "262144",
        "pkt_size": "1316",
        "connect_timeout": "2000",
        "lossmaxttl": "40",
    }
    # En modo caller hacia MediaMTX se suprime smoother=live para erradicar el retardo artificial de pacing
    if mode != "caller" and not zerolatency:
        params["smoother"] = "live"
    if streamid:
        params["streamid"] = streamid
    if passphrase:
        params["passphrase"] = passphrase
    query = urllib.parse.urlencode(params, safe=":")
    return f"srt://{host}:{port}?{query}"


def build_client_urls(
    protocol: str,
    host: str,
    port: int,
    cam_id: str,
    passphrase: str = "",
    mediamtx_port: int = 8890,
    udp_mode: str = "multicast",
) -> Dict[str, str]:
    """
    Construye las URLs canónicas y limpias para clientes (OBS/vMix) y reproductores como VLC.
    Garantiza sintaxis RFC 3986 (/?...) para SRT y prefijo @ para UDP en VLC sin parámetros de FFmpeg.
    """
    clean_cam_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(cam_id))
    clean_host = host.strip() or "127.0.0.1"

    if protocol == "srt":
        query_parts = [f"streamid=read:{clean_cam_id}"]
        if passphrase:
            query_parts.append(f"passphrase={urllib.parse.quote(passphrase)}")
        query = "&".join(query_parts)
        url = f"srt://{clean_host}:{mediamtx_port}/?{query}"
        return {"connect_url": url, "vlc_url": url}

    if protocol == "udp_unicast" or udp_mode == "unicast":
        target = "127.0.0.1" if clean_host in ("127.0.0.1", "localhost") else clean_host
        return {
            "connect_url": f"udp://{target}:{port}",
            "vlc_url": f"udp://@{target}:{port}",
        }

    # Default UDP Multicast
    ip_last = (int(port) % 200) + 1
    mcast_ip = f"239.255.0.{ip_last}"
    return {
        "connect_url": f"udp://{mcast_ip}:{port}",
        "vlc_url": f"udp://@{mcast_ip}:{port}",
    }


class StreamProc:
    """Encapsula el proceso de transmisión individual y su máquina de estados asociada."""

    def __init__(self, device_path: str):
        self.device_path = device_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state: State = State.STOPPED
        self.started_at: Optional[datetime] = None
        self.error_count: int = 0
        self.next_retry_at: Optional[datetime] = None
        self.manual_intervention_required: bool = False
        self.recovery_task: Optional[asyncio.Task] = None
        self.logs: deque = deque(maxlen=300)
        self._stop_evt = asyncio.Event()
        self._log_task: Optional[asyncio.Task] = None
        self._stdout_task: Optional[asyncio.Task] = None
        self.config: Dict[str, Any] = {}
        self.lock = asyncio.Lock()

        # Telemetría en vivo para el HUD
        self.current_fps: float = 0.0
        self.current_bitrate_kbps: float = 0.0
        self.current_speed: str = "1.0x"
        self.current_dropped_frames: int = 0
        self.total_frames: int = 0
        self.using_fallback_cpu: bool = False
        self.is_connected: bool = True
        self.per_stream_encoder: Optional[str] = None
        self.last_error_category: ErrorCategory = ErrorCategory.UNKNOWN
        self.last_transition: Optional[datetime] = None
        self.zero_fps_since: Optional[datetime] = None

    async def read_progress(self, stream: asyncio.StreamReader) -> None:
        """
        Lee continuamente el stream stdout de FFmpeg generado por '-progress pipe:1'.
        Parsea líneas 'key=value' deterministas sin expresiones regulares.
        Evita bloqueos de buffer del sistema operativo (pipe deadlock en Windows).
        """
        current_data: Dict[str, str] = {}
        try:
            while not self._stop_evt.is_set():
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                if "=" in line_str:
                    k, v = line_str.split("=", 1)
                    current_data[k.strip()] = v.strip()

                if line_str.startswith("progress="):
                    # Bloque de progreso emitido por FFmpeg
                    fps_val = current_data.get("fps")
                    if fps_val:
                        try:
                            self.current_fps = float(fps_val)
                        except ValueError:
                            pass

                    bitrate_val = current_data.get("bitrate")
                    if bitrate_val:
                        try:
                            clean_br = bitrate_val.replace("kbits/s", "").replace("k", "").strip()
                            self.current_bitrate_kbps = float(clean_br)
                        except ValueError:
                            pass

                    speed_val = current_data.get("speed")
                    if speed_val:
                        self.current_speed = speed_val

                    drop_val = current_data.get("drop_frames")
                    if drop_val:
                        try:
                            self.current_dropped_frames = int(drop_val)
                        except ValueError:
                            pass

                    frame_val = current_data.get("frame")
                    if frame_val:
                        try:
                            self.total_frames = int(frame_val)
                        except ValueError:
                            pass

                    current_data.clear()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[{self.device_path}] Lector de progreso finalizado: {e}")

    def transition_to(self, new_state: State) -> None:
        """Formaliza la transición de estados de la máquina de estados del stream."""
        logger.debug(f"[{self.device_path}] Transición de estado: {self.state} -> {new_state}")
        self.state = new_state
        self.last_transition = datetime.now()

    @property
    def permanent_failure(self) -> bool:
        return self.manual_intervention_required

    @permanent_failure.setter
    def permanent_failure(self, val: bool) -> None:
        self.manual_intervention_required = val

    def clear_failure(self) -> None:
        """Limpia el estado de intervención manual y resetea contadores para permitir reintentos."""
        self.manual_intervention_required = False
        self.error_count = 0
        self.next_retry_at = None
        self.zero_fps_since = None
        self.last_error_category = ErrorCategory.UNKNOWN
        if self.state in (State.ERROR, State.MANUAL_INTERVENTION_REQUIRED):
            self.transition_to(State.STOPPED)

    def log(self, line: str) -> None:
        clean_line = sanitize_log_line(line)
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {clean_line}")

    def get_logs(self, n: int = 100) -> List[str]:
        return list(self.logs)[-n:]

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.returncode is None
