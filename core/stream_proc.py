# ==============================================================================
# RTMS — Real-Time Multicam System
# Definición de procesos y máquinas de estados para flujos de transmisión.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Máquina de estados, categorías de error y proceso de streaming individual."""

import asyncio
import logging
import os
import re
import shutil
import subprocess
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
    """Calcula y retorna la URL multicast UDP para el puerto indicado con buffer optimizado de baja latencia y TTL de red local."""
    p = int(port)
    if 9000 <= p <= 9200:
        ip_last_octet = (p - 9000) + 1
    else:
        ip_last_octet = ((p - 1024) % 250) + 1
    return f"udp://239.255.0.{ip_last_octet}:{port}?pkt_size=1316&ttl=16&buffer_size=65536&overrun_nonfatal=1&fifo_size=5000"


def build_unicast_url(port: int, host: str = "127.0.0.1") -> str:
    """Calcula y retorna la URL unicast UDP local/remota con buffer optimizado de baja latencia."""
    clean_host = host.strip() or "127.0.0.1"
    return f"udp://{clean_host}:{port}?pkt_size=1316&buffer_size=65536&overrun_nonfatal=1&fifo_size=5000"


def build_stream_url(
    protocol: str,
    port: int,
    passphrase: str = "",
    mode: str = "listener",
    latency_ms: Optional[int] = None,
    zerolatency: bool = True,
    streamid: Optional[str] = None,
    udp_mode: str = "unicast",
    udp_host: str = "127.0.0.1",
) -> str:
    """Construye la URL normalizada de transmisión para SRT o UDP con parámetros optimizados de baja latencia."""
    if protocol == "udp_unicast" or (protocol == "udp" and udp_mode == "unicast"):
        return build_unicast_url(port, host=udp_host)
    if protocol == "udp":
        return build_multicast_url(port)

    # Protocolo SRT
    if zerolatency:
        effective_latency_ms = 10  # 10ms para loopback localhost (v2.8.2)
    else:
        effective_latency_ms = int(latency_ms) if latency_ms is not None else 120
    latency_us = effective_latency_ms * 1000

    host = "0.0.0.0" if mode == "listener" else "127.0.0.1"
    # En modo caller hacia MediaMTX y transmisiones en vivo, tlpktdrop debe ser 1
    # para evitar retardo/ping acumulado infinito y rechazo ERROR:ROGUE en gosrt.
    drop_flag = "1" if (mode == "caller" or zerolatency) else "0"
    buf_size = "65536" if zerolatency else "262144"
    params = {
        "mode": mode,
        "latency": str(latency_us),
        "transtype": "live",
        "tlpktdrop": drop_flag,
        "sndbuf": buf_size,
        "rcvbuf": buf_size,
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
    protocol: str = "udp",
    host: str = "127.0.0.1",
    port: int = 9000,
    cam_id: Optional[str] = None,
    passphrase: str = "",
    mediamtx_port: int = 8890,
    udp_mode: str = "unicast",
    latency_ms: Optional[int] = None,
    zerolatency: bool = True,
    network_type: str = "wired",
    local_ip: Optional[str] = None,
    udp_host: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construye las URLs canónicas y optimizadas para clientes (OBS/vMix, WebRTC WHEP y VLC).
    Soporta bifurcación de red cableada (15ms) vs Wi-Fi (50ms) y expone la URL WHEP para sub-30ms.
    Mantiene compatibilidad total con todas las firmas y claves históricas de RTMS.
    """
    # Detección polimórfica de argumentos: si el primer argumento es un cam_id (no un protocolo conocido)
    if protocol not in ("srt", "udp", "udp_unicast", "rtp") and cam_id is None:
        actual_cam_id = protocol
        clean_host = (local_ip or host).strip() or "127.0.0.1"
        actual_proto = "udp"
    else:
        actual_cam_id = cam_id or f"cam_{port}"
        clean_host = (local_ip or host).strip() or "127.0.0.1"
        actual_proto = protocol

    clean_cam_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(actual_cam_id))

    dest_ip = (udp_host or host or "127.0.0.1").strip()
    is_loopback = dest_ip in ("127.0.0.1", "localhost")

    if latency_ms is not None:
        srt_lat_ms = int(latency_ms)
    elif zerolatency:
        srt_lat_ms = 50 if str(network_type).lower() == "wifi" else 15
    else:
        srt_lat_ms = 120
    latency_us = srt_lat_ms * 1000

    query_parts = [
        f"streamid=read:{clean_cam_id}",
        f"latency={latency_us}",
        "rcvbuf=65536",
        "tlpktdrop=1",
    ]
    if passphrase:
        query_parts.append(f"passphrase={urllib.parse.quote(passphrase)}")
    query = "&".join(query_parts)
    srt_url = f"srt://{clean_host}:{mediamtx_port}?{query}"
    webrtc_url = f"http://{clean_host}:8889/{clean_cam_id}"

    publish_url = ""
    receive_url = ""

    if actual_proto == "srt":
        connect_url = srt_url
        vlc_url = srt_url
        publish_url = f"srt://127.0.0.1:{mediamtx_port}?streamid=publish:{clean_cam_id}"
        receive_url = srt_url
    elif actual_proto == "rtp":
        receive_url = f"rtp://{dest_ip}:{port}"
        connect_url = receive_url
        vlc_url = receive_url
        publish_url = receive_url
    elif actual_proto == "udp_unicast" or udp_mode == "unicast":
        receive_url = f"udp://127.0.0.1:{port}" if is_loopback else f"udp://{dest_ip}:{port}"
        connect_url = receive_url
        vlc_url = f"udp://@:{port}"
        publish_url = f"udp://{dest_ip}:{port}"
    else:
        # Default UDP Multicast
        p = int(port)
        if 9000 <= p <= 9200:
            ip_last = (p - 9000) + 1
        else:
            ip_last = ((p - 1024) % 250) + 1
        mcast_ip = f"239.255.0.{ip_last}"
        connect_url = f"udp://{mcast_ip}:{port}"
        vlc_url = f"udp://@{mcast_ip}:{port}"
        publish_url = connect_url
        receive_url = vlc_url

    vlc_caching_ms = 300
    vlc_command = f'vlc.exe "{vlc_url}" :network-caching={vlc_caching_ms} :drop-late-frames :skip-frames'

    return {
        "srt": srt_url,
        "webrtc": webrtc_url,
        "udp": connect_url if (actual_proto in ("udp", "udp_unicast")) else f"udp://{clean_host}:{port}",
        "rtp": connect_url if actual_proto == "rtp" else f"rtp://{dest_ip}:{port}",
        "obs_url": connect_url,
        "publish_url": publish_url,
        "receive_url": receive_url,
        "udp_host": dest_ip,
        "connect_url": connect_url,
        "vlc_url": vlc_url,
        "vlc_command": vlc_command,
        "vlc_caching_ms": vlc_caching_ms,
    }


def get_vlc_binary_path() -> Optional[str]:
    """Retorna la ruta al ejecutable VLC si está instalado en el sistema."""
    vlc_candidates = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    sys_vlc = shutil.which("vlc")
    if sys_vlc:
        vlc_candidates.insert(0, sys_vlc)

    for cand in vlc_candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


def generate_vlc_xspf_playlist(
    stream_url: str,
    title: str = "RTMS Stream",
    caching_ms: int = 300,
) -> str:
    """Genera una lista de reproducción XML XSPF estándar con metadatos y opciones seguras de baja latencia para VLC."""
    safe_title = str(title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    safe_url = str(stream_url).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    opts = [
        f"        <vlc:option>network-caching={caching_ms}</vlc:option>",
        "        <vlc:option>drop-late-frames</vlc:option>",
        "        <vlc:option>skip-frames</vlc:option>",
    ]
    opts_str = "\n".join(opts)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- RTMS low-latency: safe monitoring profile calibrated to 300ms -->\n"
        '<playlist version="1" xmlns="http://xspf.org/ns/0/" xmlns:vlc="http://www.videolan.org/vlc/playlist/ns/0/">\n'
        f"  <title>{safe_title}</title>\n"
        "  <trackList>\n"
        "    <track>\n"
        f"      <location>{safe_url}</location>\n"
        f"      <title>{safe_title} (Baja Latencia RTMS)</title>\n"
        '      <extension application="http://www.videolan.org/vlc/playlist/0">\n'
        f"{opts_str}\n"
        "      </extension>\n"
        "    </track>\n"
        "  </trackList>\n"
        "</playlist>\n"
    )


def launch_vlc_player(vlc_url: str, caching_ms: int = 300) -> bool:
    """Ejecuta VLC Player localmente con parámetros seguros de baja latencia (300ms anti-congelamiento)."""
    vlc_bin = get_vlc_binary_path()
    if not vlc_bin:
        logger.warning("No se encontró el ejecutable de VLC en el sistema.")
        return False

    cmd = [
        vlc_bin,
        vlc_url,
        f":network-caching={caching_ms}",
        ":drop-late-frames",
        ":skip-frames",
    ]
    try:
        subprocess.Popen(cmd, close_fds=True)
        logger.info("VLC Player lanzado exitosamente (:network-caching=%d)", caching_ms)
        return True
    except Exception as e:
        logger.error(f"Error lanzando VLC Player: {e}")
        return False


def generate_rtp_sdp(
    host: str = "127.0.0.1",
    port: int = 9000,
    payload_type: int = 96,
    codec: str = "H264",
    clock_rate: int = 90000,
) -> str:
    """Genera archivo de sesión SDP para clientes RTP (OBS Studio, VLC)."""
    return (
        "v=0\r\n"
        f"o=- 0 0 IN IP4 {host}\r\n"
        "s=RTMS RTP Stream\r\n"
        f"c=IN IP4 {host}\r\n"
        "t=0 0\r\n"
        f"m=video {port} RTP/AVP {payload_type}\r\n"
        f"a=rtpmap:{payload_type} {codec}/{clock_rate}\r\n"
    )


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
        self.marked_for_removal: bool = False
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
        self.last_progress_at: Optional[datetime] = None
        self.mjpeg_supported: Optional[bool] = None
        self.mjpeg_input_failed: bool = False
        self.dshow_options_failed: bool = False
        self.fps_fallback_attempted: bool = False

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
                    self.last_progress_at = datetime.now()
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
        self.last_progress_at = None
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
