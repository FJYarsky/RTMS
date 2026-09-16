# ==============================================================================
# RTMS — Real-Time Multicam System
# Gestión de transmisiones, supervisión de procesos FFmpeg y sincronización de hardware DirectShow
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import asyncio
import sys
import re
import logging
import urllib.parse
from enum import Enum
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from core.sanitizer import sanitize_command_for_log, sanitize_log_line, sanitize_url
from .hardware import get_directshow_devices, get_ffmpeg_bin, has_ffmpeg_binary, _FFMPEG_BIN, hardware_detector
from .config_mgr import get_or_allocate_camera_config
from .port_mgr import port_manager

logger = logging.getLogger("rtms.ffmpeg_mgr")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW

class ErrorCategory(str, Enum):
    """Taxonomía formal de categorías de error para diagnósticos y políticas de reconexión (P1-07)."""
    CONFIGURATION  = "configuration"
    DEVICE         = "device"
    ENCODER        = "encoder"
    NETWORK        = "network"
    PORT_COLLISION = "port_collision"
    PROCESS        = "process"
    AUTHENTICATION = "authentication"
    UNKNOWN        = "unknown"

class State(str, Enum):
    STOPPED                      = "stopped"
    STARTING                     = "starting"
    RUNNING                      = "running"
    ERROR                        = "error"
    RESTARTING                   = "restarting"
    RECOVERING                   = "recovering"
    STOPPING                     = "stopping"
    DISCONNECTED                 = "disconnected"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"

def build_multicast_url(port: int) -> str:
    """Calcula y retorna la URL multicast UDP para el puerto indicado (N2)."""
    ip_last_octet = (int(port) % 200) + 1
    return f"udp://239.255.0.{ip_last_octet}:{port}?pkt_size=1316&buffer_size=65535"

def build_stream_url(
    protocol: str,
    port: int,
    passphrase: str = "",
    mode: str = "listener",
    latency_ms: int = 120,
    zerolatency: bool = True
) -> str:
    """Construye la URL normalizada de transmisión para SRT o UDP con codificación segura (N2, N9)."""
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
        "smoother": "live",
        "tlpktdrop": drop_flag,
        "sndbuf": "262144",
        "rcvbuf": "262144"
    }
    if passphrase:
        params["passphrase"] = passphrase
    query = urllib.parse.urlencode(params)
    return f"srt://{host}:{port}?{query}"

class StreamProc:
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
        self.config: Dict[str, Any] = {}
        self.lock = asyncio.Lock()

        # Telemetría en vivo para el HUD
        self.current_fps: float = 0.0
        self.current_bitrate_kbps: float = 0.0
        self.current_speed: str = "1.0x"
        self.using_fallback_cpu: bool = False
        self.is_connected: bool = True
        self.per_stream_encoder: Optional[str] = None
        self.last_error_category: ErrorCategory = ErrorCategory.UNKNOWN
        self.last_transition: Optional[datetime] = None

    def transition_to(self, new_state: State) -> None:
        """Formaliza la transición de estados de la máquina de estados del stream (P1-08)."""
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


class StreamManager:
    WATCHDOG_INTERVAL = 2  # Intervalo de evaluación ágil no bloqueante
    MAX_ERRORS = 5
    STABILITY_THRESHOLD_SECONDS = 60

    def __init__(self):
        self._procs: Dict[str, StreamProc] = {}
        self._watchdog_task: Optional[asyncio.Task] = None

    def get_proc(self, device_path: str) -> StreamProc:
        if device_path not in self._procs:
            self._procs[device_path] = StreamProc(device_path)
        return self._procs[device_path]

    async def detect_best_encoder(self, proc: Optional[StreamProc] = None) -> str:
        """
        Detecta el mejor codificador por hardware disponible consultando la caché global singleton.
        Evita lanzar subprocesos redundantes de prueba en cada stream (P1-03 / GPU optimization).
        """
        if proc and proc.per_stream_encoder:
            return proc.per_stream_encoder

        best = await hardware_detector.get_best_encoder()
        if proc:
            proc.per_stream_encoder = best
        return best

    async def build_command(self, cfg: Dict[str, Any], force_cpu: bool = False, proc: Optional[StreamProc] = None):
        res_map = {
            "480p": "854x480",
            "720p": "1280x720",
            "1080p": "1920x1080",
            "1440p": "2560x1440",
            "4K": "3840x2160"
        }
        video_size = res_map.get(cfg.get("resolution", "720p"), "1280x720")
        fps = cfg.get("fps", 30)
        gop = fps * 2
        bitrate = cfg.get("bitrate", 3000)
        zerolatency = cfg.get("zerolatency", True)

        bk = f"{bitrate}k"
        maxbk = f"{int(bitrate * 1.15)}k"
        bufk = f"{bitrate * 2}k"

        ffmpeg_bin = get_ffmpeg_bin()
        escaped_device = cfg.get("device_path", cfg.get("friendly_name", "")).replace(":", "\\:")

        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-stats", "-stats_period", "1",
            "-f", "dshow",
            "-rtbufsize", "150M",
            "-video_size", video_size,
            "-framerate", str(fps),
            "-i", f"video={escaped_device}",
            "-pix_fmt", "yuv420p"
        ]

        if force_cpu:
            encoder = "libx264"
        else:
            encoder = cfg.get("encoder", "auto")
            if encoder == "auto":
                encoder = await self.detect_best_encoder(proc)

        # Ajuste de flags del codificador según opción zerolatency
        if zerolatency:
            if encoder == "libx264":
                cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]
            elif encoder == "h264_nvenc":
                cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ull", "-delay", "0", "-zerolatency", "1"]
            elif encoder == "h264_amf":
                cmd += ["-c:v", "h264_amf", "-quality", "speed", "-usage", "ultralowlatency"]
            elif encoder == "h264_qsv":
                cmd += ["-c:v", "h264_qsv", "-preset", "veryfast"]
            else:
                cmd += ["-c:v", encoder]
        else:
            # Perfil equilibrado de broadcast (sin comprometer calidad innecesariamente)
            if encoder == "libx264":
                cmd += ["-c:v", "libx264", "-preset", "veryfast"]
            elif encoder == "h264_nvenc":
                cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq"]
            elif encoder == "h264_amf":
                cmd += ["-c:v", "h264_amf", "-quality", "balanced"]
            elif encoder == "h264_qsv":
                cmd += ["-c:v", "h264_qsv", "-preset", "medium"]
            else:
                cmd += ["-c:v", encoder]

        cmd += [
            "-b:v", bk, "-maxrate", maxbk, "-bufsize", bufk,
            "-g", str(gop),
            "-an"
        ]

        protocol = cfg.get("protocol", "srt")
        port = cfg.get("port", 9000)
        passphrase = cfg.get("srt_passphrase", "")
        latency_ms = int(cfg.get("srt_latency", 120))

        raw_url = build_stream_url(
            protocol=protocol,
            port=port,
            passphrase=passphrase,
            mode="listener",
            latency_ms=latency_ms,
            zerolatency=zerolatency
        )

        if zerolatency:
            cmd += [
                "-f", "mpegts",
                "-muxdelay", "0",
                "-muxpreload", "0",
                "-flush_packets", "1",
                raw_url
            ]
        else:
            cmd += [
                "-f", "mpegts",
                raw_url
            ]

        # Seguridad crítica (P0-01): Nunca retornar URL con credenciales en claro para APIs ni configs
        sanitized_url = sanitize_url(raw_url)
        return cmd, sanitized_url, encoder

    async def start_stream(self, device_path: str, force_cpu: bool = False):
        """Inicia un flujo asegurando exclusión mutua para evitar ejecuciones concurrentes."""
        proc = self.get_proc(device_path)
        async with proc.lock:
            await self._start_stream_locked(proc, force_cpu=force_cpu)

    async def _start_stream_locked(self, proc: StreamProc, force_cpu: bool = False):
        if proc.is_alive:
            logger.debug(f"Flujo {proc.device_path} ya está en ejecución.")
            return

        if not proc.is_connected:
            logger.warning(f"Cámara {proc.device_path} desconectada físicamente. No se puede iniciar.")
            proc.state = State.DISCONNECTED
            return

        if not has_ffmpeg_binary():
            proc.state = State.ERROR
            proc.log(f"ERROR: Binario FFmpeg no encontrado en {_FFMPEG_BIN} ni en PATH del sistema.")
            logger.error(f"FFmpeg no disponible para iniciar stream de {proc.device_path}")
            return

        proc.state = State.STARTING
        proc._stop_evt.clear()
        proc.using_fallback_cpu = force_cpu

        # Bloqueo por fallo de credencial (ChatGPT P0-04)
        if proc.config.get("decryption_failed"):
            logger.error(f"[{proc.device_path}] Imposible iniciar transmisión: Falló el descifrado seguro DPAPI.")
            proc.transition_to(State.MANUAL_INTERVENTION_REQUIRED)
            proc.last_error_category = ErrorCategory.AUTHENTICATION
            proc.log("ERROR CRÍTICO: Falló el descifrado de la credencial SRT. Intervención manual requerida.")
            return

        # Revalidación de puerto previo al vuelo para prevenir condiciones TOCTOU (P1-01)
        cfg_port = proc.config.get("port")
        if cfg_port and not port_manager.revalidate_port(int(cfg_port)):
            logger.warning(f"Puerto {cfg_port} ocupado en el sistema antes de iniciar {proc.device_path}. Reasignando...")
            new_port = port_manager.reallocate_if_collided(int(cfg_port))
            proc.config["port"] = new_port
            from .config_mgr import save_config, load_config
            c_all = load_config()
            if proc.device_path in c_all.get("cameras", {}):
                c_all["cameras"][proc.device_path]["port"] = new_port
                save_config(c_all)

        try:
            cmd, url, actual_encoder = await self.build_command(proc.config, force_cpu=force_cpu, proc=proc)
            proc.config["_url"] = url
            proc.config["_actual_encoder"] = actual_encoder
        except Exception as e:
            proc.state = State.ERROR
            proc.log(f"Error construyendo comando: {e}")
            logger.error(f"Error en build_command para {proc.device_path}: {e}")
            return

        clean_cmd_log = sanitize_command_for_log(cmd)
        logger.info(f"Iniciando flujo ({actual_encoder}): {clean_cmd_log}")
        proc.log(f"Iniciando ({actual_encoder}): {clean_cmd_log}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                creationflags=_WIN_FLAGS
            )
        except Exception as exc:
            proc.state = State.ERROR
            proc.log(f"ERROR al lanzar proceso: {exc}")
            if not force_cpu:
                logger.warning(f"Reintentando {proc.device_path} con fallback a CPU libx264...")
                proc.log("Reintentando con fallback a CPU libx264...")
                await asyncio.sleep(0.5)
                await self._start_stream_locked(proc, force_cpu=True)
            return

        proc.process = process
        proc.started_at = datetime.now()
        proc.state = State.RUNNING
        proc.permanent_failure = False
        proc.next_retry_at = None

        if proc._log_task and not proc._log_task.done():
            proc._log_task.cancel()
        proc._log_task = asyncio.create_task(self._collect_logs(proc.device_path, process))

    async def stop_stream(self, device_path: str, timeout: float = 2.5):
        """Detiene un flujo de forma limpia y ordenada enviando 'q' antes de terminate/kill."""
        proc = self.get_proc(device_path)
        async with proc.lock:
            await self._stop_stream_locked(proc, timeout=timeout)

    async def _stop_stream_locked(self, proc: StreamProc, timeout: float = 2.5):
        proc._stop_evt.set()
        proc.transition_to(State.STOPPING)

        # Limpieza formal de recovery_task (P1-09)
        if proc.recovery_task and not proc.recovery_task.done():
            proc.recovery_task.cancel()
            try:
                await proc.recovery_task
            except (asyncio.CancelledError, Exception):
                pass
        proc.recovery_task = None

        if proc.process and proc.process.returncode is None:
            # 1. Intento limpio: Enviar comando 'q' a stdin para cierre de socket SRT y MPEG-TS
            try:
                if proc.process.stdin:
                    proc.process.stdin.write(b'q\n')
                    await proc.process.stdin.drain()
            except Exception as e:
                logger.debug(f"Aviso al enviar 'q' a {proc.device_path}: {e}")

            # 2. Esperar período de gracia
            try:
                await asyncio.wait_for(proc.process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                # 3. Fallback: Terminate
                logger.warning(f"FFmpeg {proc.device_path} no respondió a 'q' en {timeout}s. Enviando terminate()...")
                try:
                    proc.process.terminate()
                    await asyncio.wait_for(proc.process.wait(), timeout=1.0)
                except (asyncio.TimeoutError, Exception):
                    # 4. Último recurso: Kill
                    logger.error(f"Forzando kill() en FFmpeg {proc.device_path}...")
                    try:
                        proc.process.kill()
                    except Exception:
                        pass

        if proc._log_task and not proc._log_task.done():
            proc._log_task.cancel()

        proc.transition_to(State.STOPPED)
        proc.process = None
        proc.current_fps = 0.0
        proc.current_bitrate_kbps = 0.0
        proc.log("Stream detenido limpiamente.")

    async def remove_stream(self, device_path: str) -> bool:
        """Detiene la transmisión, libera el puerto y elimina la cámara de forma permanente (P1-06)."""
        proc = self._procs.get(device_path)
        if not proc:
            # Buscar por camera_id
            for dp, p in list(self._procs.items()):
                if p.config.get("id") == device_path:
                    proc = p
                    device_path = dp
                    break

        if proc:
            await self.stop_stream(device_path)
            port = proc.config.get("port")
            if port:
                port_manager.release_port(int(port))
            if proc._log_task and not proc._log_task.done():
                proc._log_task.cancel()
            if proc.recovery_task and not proc.recovery_task.done():
                proc.recovery_task.cancel()
            self._procs.pop(device_path, None)

        # Invalidar tickets de preview asociados a esta cámara (ChatGPT P1-03)
        try:
            from api.routes import preview_ticket_mgr
            preview_ticket_mgr.invalidate_for_device(device_path)
        except Exception:
            pass

        from .config_mgr import remove_camera_config
        return remove_camera_config(device_path)

    async def _fallback_to_cpu(self, device_path: str):
        """Maneja la transición explícita de fallo de GPU a CPU sin condiciones de carrera."""
        proc = self.get_proc(device_path)
        async with proc.lock:
            if proc.using_fallback_cpu:
                return
            logger.warning(f"[{device_path}] Ejecutando transición segura de encoder GPU a CPU (libx264)...")
            proc.log("GPU encoder falló. Cambiando a CPU libx264...")
            await self._stop_stream_locked(proc, timeout=1.5)
            proc.using_fallback_cpu = True
            proc.per_stream_encoder = "libx264"
            await self._start_stream_locked(proc, force_cpu=True)

    async def stop_all(self):
        """Detiene todos los flujos activos de forma concurrente y ordenada."""
        logger.info("Deteniendo todos los flujos activos ordenadamente...")
        tasks = [self.stop_stream(dp) for dp in list(self._procs.keys())]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def emergency_stop_all(self):
        """Detención global de todas las transmisiones solicitada por el usuario."""
        logger.warning("DETENCIÓN GLOBAL DE TRANSMISIONES SOLICITADA.")
        await self.stop_all()

    async def stop_all_streams(self):
        """Alias formal para detención global de todas las transmisiones."""
        await self.emergency_stop_all()

    async def watchdog(self):
        """
        Watchdog no bloqueante con recuperación independiente por stream,
        reseteo de errores tras estabilidad y pausa ante desconexión física.
        """
        while True:
            try:
                await asyncio.sleep(self.WATCHDOG_INTERVAL)
                now = datetime.now()

                for dp, proc in list(self._procs.items()):
                    # 1. Reseteo de errores tras período de estabilidad
                    if proc.is_alive and proc.started_at:
                        uptime = (now - proc.started_at).total_seconds()
                        if uptime >= self.STABILITY_THRESHOLD_SECONDS and (proc.error_count > 0 or proc.permanent_failure):
                            logger.info(f"Flujo {dp} estable por {int(uptime)}s. Reseteando contadores de error.")
                            proc.clear_failure()
                        continue

                    # 2. Detección de caída de flujo
                    if not proc.is_alive and proc.state == State.RUNNING:
                        logger.warning(f"Flujo {dp} caído inesperadamente (error #{proc.error_count + 1}).")
                        proc.error_count += 1
                        proc.transition_to(State.ERROR)
                        backoff = min(5 * (2 ** max(0, proc.error_count - 1)), 60)
                        proc.next_retry_at = now + timedelta(seconds=backoff)

                    # 3. Lógica de reintento inteligente
                    if proc.state == State.ERROR and not proc._stop_evt.is_set():
                        # Si el hardware fue desconectado físicamente, pausar reintentos
                        if not proc.is_connected:
                            proc.transition_to(State.DISCONNECTED)
                            logger.info(f"Cámara {dp} marcada como desconectada. Reintentos pausados.")
                            continue

                        if proc.error_count <= self.MAX_ERRORS:
                            if proc.next_retry_at and now >= proc.next_retry_at:
                                logger.info(f"Watchdog recuperando {dp} (intento {proc.error_count}/{self.MAX_ERRORS})...")
                                proc.transition_to(State.RECOVERING)
                                proc.next_retry_at = None
                                force_cpu = proc.error_count >= 2
                                if proc.recovery_task and not proc.recovery_task.done():
                                    proc.recovery_task.cancel()
                                proc.recovery_task = asyncio.create_task(self.start_stream(dp, force_cpu=force_cpu))
                        else:
                            if not proc.manual_intervention_required:
                                proc.manual_intervention_required = True
                                proc.transition_to(State.MANUAL_INTERVENTION_REQUIRED)
                                logger.error(f"Flujo {dp} superó el límite de {self.MAX_ERRORS} errores. Pausado esperando intervención manual.")
                                proc.log(f"CRÍTICO: Superado límite de {self.MAX_ERRORS} errores consecutivos. Pausado esperando intervención manual.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en Watchdog: {e}")

    async def reallocate_if_collided(self, proc: StreamProc) -> int:
        """Reasigna un puerto libre ante colisión y actualiza la configuración (P1-05)."""
        proc.last_error_category = ErrorCategory.PORT_COLLISION
        cfg_port = proc.config.get("port", 9000)
        new_port = port_manager.reallocate_if_collided(int(cfg_port))
        proc.config["port"] = new_port
        from .config_mgr import save_config, load_config
        c_all = load_config()
        dp = proc.device_path
        if dp in c_all.get("cameras", {}):
            c_all["cameras"][dp]["port"] = new_port
            save_config(c_all)
        return new_port

    async def _collect_logs(self, device_path: str, process: asyncio.subprocess.Process):
        proc = self._procs.get(device_path)
        if not proc:
            return

        FATAL_PATTERNS = [
            "no such file or directory",
            "invalid data found",
            "connection refused",
            "unable to open input",
            "device not found",
            "could not find video device",
            "dshow: could not",
            "error while opening encoder",
            "bind failed",
            "address already in use"
        ]

        stats_pattern = re.compile(r"fps=\s*([0-9.]+).*bitrate=\s*([0-9.]+)kbits/s.*speed=\s*([0-9.x]+)")

        try:
            async for raw in process.stderr:
                raw_line = raw.decode("utf-8", errors="replace").strip()
                if not raw_line:
                    continue

                m = stats_pattern.search(raw_line)
                if m:
                    try:
                        proc.current_fps = float(m.group(1))
                        proc.current_bitrate_kbps = float(m.group(2))
                        proc.current_speed = m.group(3)
                    except ValueError:
                        pass
                    continue

                # Sanitizar antes de guardar en el buffer de logs en memoria
                clean_line = sanitize_log_line(raw_line)
                proc.log(clean_line)

                line_lower = raw_line.lower()

                # Detección de colisión de socket en runtime (P1-05)
                if "bind failed" in line_lower or "address already in use" in line_lower:
                    logger.warning(f"[{device_path}] Colisión de socket detectada en FFmpeg: {clean_line}. Reasignando puerto...")
                    await self.reallocate_if_collided(proc)

                if any(pat in line_lower for pat in FATAL_PATTERNS):
                    logger.warning(f"[{device_path}] Error en FFmpeg: {clean_line}")

                    # Clasificación formal de categoría de error (P1-07)
                    if "could not find video device" in line_lower or "device not found" in line_lower or "dshow: could not" in line_lower:
                        proc.last_error_category = ErrorCategory.DEVICE
                    elif "error while opening encoder" in line_lower:
                        proc.last_error_category = ErrorCategory.ENCODER
                    elif "connection refused" in line_lower or "bind failed" in line_lower:
                        proc.last_error_category = ErrorCategory.NETWORK
                    else:
                        proc.last_error_category = ErrorCategory.PROCESS

                    if "error while opening encoder" in line_lower and not proc.using_fallback_cpu:
                        asyncio.create_task(self._fallback_to_cpu(device_path))
                        return

                    if proc.state == State.RUNNING:
                        proc.transition_to(State.ERROR)
                        proc.error_count += 1
                        backoff = min(5 * (2 ** max(0, proc.error_count - 1)), 60)
                        proc.next_retry_at = datetime.now() + timedelta(seconds=backoff)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error leyendo logs de {device_path}: {e}")

    async def start_periodic_hardware_sync(self, interval: int = 20):
        """Tarea en segundo plano que sondea periódicamente cambios en dispositivos DirectShow (hotplug)."""
        while True:
            try:
                await asyncio.sleep(interval)
                await self.sync_streams_with_hardware()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en sincronización periódica de hardware: {e}")

    async def sync_streams_with_hardware(self):
        """Sincroniza el inventario de cámaras con el hardware DirectShow detectado."""
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self.watchdog())

        devices = await get_directshow_devices()
        detected_paths = {d["device_path"]: d["friendly_name"] for d in devices}

        # 1. Actualizar estado de desconexión para cámaras desaparecidas
        for dp, proc in self._procs.items():
            was_connected = proc.is_connected
            proc.is_connected = dp in detected_paths
            if was_connected and not proc.is_connected:
                logger.warning(f"Cámara {dp} desapareció del sistema. Marcando como DISCONNECTED.")
                proc.transition_to(State.DISCONNECTED)
                if proc.is_alive:
                    asyncio.create_task(self.stop_stream(dp, timeout=1.0))

        # 2. Registrar y actualizar dispositivos presentes (omitiendo ignored_devices Claude N1)
        from .config_mgr import load_config
        active_cfg = load_config()
        ignored_devs = set(active_cfg.get("ignored_devices", []))

        for d in devices:
            dp = d["device_path"]
            if dp in ignored_devs:
                continue
            proc = self.get_proc(dp)
            was_disconnected = not proc.is_connected
            proc.config = get_or_allocate_camera_config(dp, d["friendly_name"])
            proc.is_connected = True

            # Si la cámara se reconectó y tiene autoarranque habilitado
            if was_disconnected and proc.config.get("auto_start", False) and not proc._stop_evt.is_set():
                logger.info(f"Cámara {dp} reconectada. Reiniciando transmisión automática...")
                proc.error_count = 0
                proc.permanent_failure = False
                asyncio.create_task(self.start_stream(dp))
            elif proc.config.get("auto_start", False) and proc.state == State.STOPPED and not proc._stop_evt.is_set():
                asyncio.create_task(self.start_stream(dp))

    @property
    def has_active_streams(self) -> bool:
        """Indica si existe al menos un proceso de transmisión activo en ejecución."""
        return any(proc.is_alive for proc in self._procs.values())

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        statuses = []
        for dp, proc in self._procs.items():
            cfg = proc.config or {}
            raw_pass = cfg.get("srt_passphrase", "")
            raw_url = cfg.get("_url", "")
            statuses.append({
                "id": cfg.get("id", ""),
                "device_path": dp,
                "friendly_name": cfg.get("friendly_name", dp),
                "resolution": cfg.get("resolution", "720p"),
                "fps": cfg.get("fps", 30),
                "bitrate": cfg.get("bitrate", 3000),
                "protocol": cfg.get("protocol", "srt"),
                "port": cfg.get("port", 9000),
                "encoder": cfg.get("encoder", "auto"),
                "actual_encoder": cfg.get("_actual_encoder", proc.per_stream_encoder or "auto"),
                "srt_latency": cfg.get("srt_latency", 120),
                "srt_passphrase": "••••••••" if raw_pass else "",
                "has_passphrase": bool(raw_pass),
                "decryption_failed": bool(cfg.get("decryption_failed", False)),
                "url": sanitize_url(raw_url),
                "auto_start": cfg.get("auto_start", True),
                "zerolatency": cfg.get("zerolatency", True),
                "is_virtual": cfg.get("is_virtual", False),
                "is_connected": proc.is_connected,
                "permanent_failure": proc.permanent_failure,
                "last_error_category": proc.last_error_category.value,
                "status": {
                    "state": proc.state.value if isinstance(proc.state, State) else str(proc.state),
                    "current_fps": proc.current_fps,
                    "current_bitrate_kbps": proc.current_bitrate_kbps,
                    "current_speed": proc.current_speed,
                    "error_count": proc.error_count,
                    "using_fallback_cpu": proc.using_fallback_cpu,
                    "manual_intervention_required": proc.permanent_failure,
                    "started_at": proc.started_at.isoformat() if proc.started_at else None,
                    "uptime_seconds": (datetime.now() - proc.started_at).total_seconds() if proc.is_alive and proc.started_at else None
                }
            })
        return statuses

# Instancia global única
stream_manager = StreamManager()

async def sync_streams_with_hardware():
    await stream_manager.sync_streams_with_hardware()

def get_all_stream_statuses() -> List[Dict[str, Any]]:
    return stream_manager.get_all_statuses()
