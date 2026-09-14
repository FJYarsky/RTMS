# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.3
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import asyncio
import os
import sys
import re
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any

from .hardware import get_directshow_devices
from .config_mgr import get_or_allocate_camera_config, is_virtual_device

logger = logging.getLogger("rtms.ffmpeg_mgr")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FFMPEG_BIN = os.path.join(_BASE_DIR, "bin", "ffmpeg.exe")

class State:
    STOPPED    = "stopped"
    STARTING   = "starting"
    RUNNING    = "running"
    ERROR      = "error"
    RESTARTING = "restarting"

class StreamProc:
    def __init__(self, device_path: str):
        self.device_path = device_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state: str = State.STOPPED
        self.started_at: Optional[datetime] = None
        self.error_count: int = 0
        self.logs: deque = deque(maxlen=300)
        self._stop_evt = asyncio.Event()
        self._log_task: Optional[asyncio.Task] = None
        self.config: Dict[str, Any] = {}
        
        # Telemetría en vivo para el HUD
        self.current_fps: float = 0.0
        self.current_bitrate_kbps: float = 0.0
        self.current_speed: str = "1.0x"
        self.using_fallback_cpu: bool = False
        self.is_connected: bool = True

    def log(self, line: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {line}")

    def get_logs(self, n: int = 100) -> List[str]:
        return list(self.logs)[-n:]

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.returncode is None


class StreamManager:
    WATCHDOG_INTERVAL = 10
    MAX_ERRORS = 5

    def __init__(self):
        self._procs: Dict[str, StreamProc] = {}
        self.best_encoder_cache: Optional[str] = None
        self._watchdog_task: Optional[asyncio.Task] = None

    def get_proc(self, device_path: str) -> StreamProc:
        if device_path not in self._procs:
            self._procs[device_path] = StreamProc(device_path)
        return self._procs[device_path]

    async def detect_best_encoder(self) -> str:
        """
        Detecta el mejor codificador por hardware usando una resolución válida
        (640x360) para no disparar restricciones de tamaño mínimo de NVIDIA NVENC.
        """
        if self.best_encoder_cache:
            return self.best_encoder_cache

        encoders_to_test = ["h264_nvenc", "h264_qsv", "h264_amf"]
        
        logger.info("Detectando codificador por hardware óptimo...")
        for enc in encoders_to_test:
            try:
                proc = await asyncio.create_subprocess_exec(
                    _FFMPEG_BIN, "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.1",
                    "-pix_fmt", "yuv420p",
                    "-c:v", enc, "-f", "null", "-",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    creationflags=_WIN_FLAGS
                )
                await proc.wait()
                if proc.returncode == 0:
                    logger.info(f"Codificador por hardware validado: {enc}")
                    self.best_encoder_cache = enc
                    return enc
            except Exception as e:
                logger.debug(f"Encoder {enc} falló prueba: {e}")
                
        logger.info("No se detectó GPU compatible. Usando codificador CPU (libx264).")
        self.best_encoder_cache = "libx264"
        return "libx264"

    async def build_command(self, cfg: Dict[str, Any], force_cpu: bool = False):
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
        
        bk = f"{bitrate}k"
        maxbk = f"{int(bitrate * 1.15)}k"
        bufk = f"{bitrate * 2}k"

        if not os.path.exists(_FFMPEG_BIN):
            raise FileNotFoundError(f"FFmpeg no encontrado en: {_FFMPEG_BIN}")

        escaped_device = cfg.get("device_path", cfg.get("friendly_name", "")).replace(":", "\\:")
        
        cmd = [
            _FFMPEG_BIN,
            "-hide_banner",
            "-stats", "-stats_period", "1",
            "-f", "dshow",
            "-rtbufsize", "150M",
            "-video_size", video_size,
            "-framerate", str(fps),
            "-i", f"video={escaped_device}",
            "-pix_fmt", "yuv420p"  # Conversión universal a YUV420P
        ]

        if force_cpu:
            encoder = "libx264"
        else:
            encoder = cfg.get("encoder", "auto")
            if encoder == "auto":
                encoder = await self.detect_best_encoder()

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

        cmd += [
            "-b:v", bk, "-maxrate", maxbk, "-bufsize", bufk,
            "-g", str(gop),
            "-an"
        ]

        protocol = cfg.get("protocol", "srt")
        port = cfg.get("port", 9000)
        
        if protocol == "srt":
            latency_ms = int(cfg.get("srt_latency", 120))
            latency_us = latency_ms * 1000
            
            url = (
                f"srt://0.0.0.0:{port}"
                f"?mode=listener"
                f"&latency={latency_us}"
                f"&transtype=live"
                f"&smoother=live"
                f"&tlpktdrop=1"
                f"&sndbuf=262144"
                f"&rcvbuf=262144"
            )
            passphrase = cfg.get("srt_passphrase", "")
            if passphrase:
                url += f"&passphrase={passphrase}"
                
            cmd += [
                "-f", "mpegts",
                "-muxdelay", "0",
                "-muxpreload", "0",
                "-flush_packets", "1",
                url
            ]
        else:
            ip_last_octet = (port % 200) + 1
            url = f"udp://239.255.0.{ip_last_octet}:{port}?pkt_size=1316&buffer_size=65535"
            cmd += [
                "-f", "mpegts",
                "-muxdelay", "0",
                "-muxpreload", "0",
                "-flush_packets", "1",
                url
            ]

        return cmd, url, encoder

    async def start_stream(self, device_path: str, force_cpu: bool = False):
        proc = self.get_proc(device_path)
        
        if proc.is_alive:
            return

        proc.state = State.STARTING
        proc._stop_evt.clear()
        proc.using_fallback_cpu = force_cpu

        try:
            cmd, url, actual_encoder = await self.build_command(proc.config, force_cpu=force_cpu)
            proc.config["_url"] = url
            proc.config["_actual_encoder"] = actual_encoder
        except Exception as e:
            proc.state = State.ERROR
            proc.log(f"Error construyendo comando: {e}")
            logger.error(f"Error en build_command para {device_path}: {e}")
            return
        
        logger.info(f"Iniciando flujo ({actual_encoder}): {' '.join(cmd)}")
        proc.log(f"Iniciando ({actual_encoder}): " + " ".join(cmd))

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
                logger.warning(f"Reintentando {device_path} con fallback a CPU libx264...")
                proc.log("Reintentando con fallback a CPU libx264...")
                await asyncio.sleep(1)
                await self.start_stream(device_path, force_cpu=True)
            return

        proc.process = process
        proc.started_at = datetime.now()
        proc.state = State.RUNNING

        if proc._log_task and not proc._log_task.done():
            proc._log_task.cancel()
        proc._log_task = asyncio.create_task(self._collect_logs(device_path, process))

        proc.log(f"Flujo iniciado con éxito (PID={process.pid})")

    async def stop_stream(self, device_path: str):
        """Detención limpia y ordenada (Graceful Shutdown) enviando 'q' a FFmpeg."""
        proc = self._procs.get(device_path)
        if not proc:
            return

        proc._stop_evt.set()

        if proc.is_alive and proc.process:
            try:
                if proc.process.stdin and not proc.process.stdin.is_closing():
                    try:
                        proc.process.stdin.write(b"q\n")
                        await proc.process.stdin.drain()
                    except Exception:
                        pass
                
                try:
                    await asyncio.wait_for(proc.process.wait(), timeout=1.5)
                except asyncio.TimeoutError:
                    proc.process.terminate()
                    try:
                        await asyncio.wait_for(proc.process.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        proc.process.kill()
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.warning(f"Excepción deteniendo stream {device_path}: {e}")

        if proc._log_task and not proc._log_task.done():
            proc._log_task.cancel()

        proc.state = State.STOPPED
        proc.process = None
        proc.current_fps = 0.0
        proc.current_bitrate_kbps = 0.0
        proc.log("Stream detenido limpiamente.")

    async def emergency_stop_all(self):
        logger.warning("DETENCIÓN DE EMERGENCIA SOLICITADA. Deteniendo todos los flujos...")
        tasks = [self.stop_stream(dp) for dp in list(self._procs.keys())]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def watchdog(self):
        """Watchdog robusto con reseteo de errores tras estabilidad y backoff exponencial."""
        while True:
            try:
                await asyncio.sleep(self.WATCHDOG_INTERVAL)
                for dp, proc in list(self._procs.items()):
                    if proc._stop_evt.is_set():
                        continue

                    # 1. Reseteo de errores si el flujo estuvo estable por más de 60 segundos
                    if proc.is_alive and proc.state == State.RUNNING:
                        if proc.started_at:
                            running_seconds = (datetime.now() - proc.started_at).total_seconds()
                            if running_seconds >= 60 and proc.error_count > 0:
                                logger.info(f"Flujo {dp} estable ({int(running_seconds)}s). Reseteando error_count a 0.")
                                proc.error_count = 0
                        continue

                    # 2. Detección de caída de flujo
                    if not proc.is_alive and proc.state == State.RUNNING:
                        logger.warning(f"Flujo {dp} caído inesperadamente (error #{proc.error_count + 1}).")
                        proc.error_count += 1
                        proc.state = State.ERROR

                    # 3. Lógica de reintento inteligente
                    if proc.state == State.ERROR and not proc._stop_evt.is_set():
                        # Si el hardware fue desconectado físicamente, esperar a que vuelva a aparecer
                        if not proc.is_connected:
                            logger.info(f"Cámara {dp} desconectada físicamente. Watchdog esperando reconexión por sondeo.")
                            continue

                        if proc.error_count <= self.MAX_ERRORS:
                            # Backoff exponencial: 5s, 10s, 20s, 40s, máx 60s
                            backoff_delay = min(5 * (2 ** max(0, proc.error_count - 1)), 60)
                            logger.info(f"Watchdog reintentando {dp} en {backoff_delay}s (intento {proc.error_count}/{self.MAX_ERRORS})...")
                            proc.state = State.RESTARTING
                            await asyncio.sleep(backoff_delay)
                            try:
                                force_cpu = proc.error_count >= 2
                                await self.start_stream(dp, force_cpu=force_cpu)
                            except Exception as e:
                                logger.error(f"Fallo reinicio de {dp}: {e}")
                        else:
                            logger.error(f"Flujo {dp} superó el límite de {self.MAX_ERRORS} errores. Detenido definitivamente.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en Watchdog: {e}")

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
            "error while opening encoder"
        ]

        stats_pattern = re.compile(r"fps=\s*([0-9.]+).*bitrate=\s*([0-9.]+)kbits/s.*speed=\s*([0-9.x]+)")

        try:
            async for raw in process.stderr:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                m = stats_pattern.search(line)
                if m:
                    try:
                        proc.current_fps = float(m.group(1))
                        proc.current_bitrate_kbps = float(m.group(2))
                        proc.current_speed = m.group(3)
                    except ValueError:
                        pass
                    continue

                proc.log(line)

                line_lower = line.lower()
                if any(pat in line_lower for pat in FATAL_PATTERNS):
                    logger.warning(f"[{device_path}] Error fatal detectado en FFmpeg: {line}")
                    if proc.state == State.RUNNING:
                        proc.state = State.ERROR
                        proc.error_count += 1
                        
                        if "error while opening encoder" in line_lower and not proc.using_fallback_cpu:
                            logger.warning(f"Activando fallback automático a CPU libx264 para {device_path}...")
                            asyncio.create_task(self.start_stream(device_path, force_cpu=True))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error leyendo logs de {device_path}: {e}")

    async def sync_streams_with_hardware(self):
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self.watchdog())

        devices = await get_directshow_devices()
        detected_paths = {d["device_path"]: d["friendly_name"] for d in devices}

        for dp, proc in self._procs.items():
            proc.is_connected = dp in detected_paths

        for d in devices:
            dp = d["device_path"]
            proc = self.get_proc(dp)
            proc.config = get_or_allocate_camera_config(dp, d["friendly_name"])
            proc.is_connected = True

            if proc.config.get("auto_start", False) and proc.state == State.STOPPED and not proc._stop_evt.is_set():
                logger.info(f"Autoarranque desatendido: iniciando {d['friendly_name']}...")
                asyncio.create_task(self.start_stream(dp))

    async def start_periodic_hardware_sync(self):
        while True:
            try:
                await asyncio.sleep(20)
                await self.sync_streams_with_hardware()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error en periodic_hardware_sync: {e}")

    def get_all_stream_statuses(self) -> list:
        result = []
        for dp, proc in self._procs.items():
            conf = proc.config
            uptime = None
            if proc.started_at and proc.state == State.RUNNING:
                uptime = (datetime.now() - proc.started_at).total_seconds()

            friendly_name = conf.get("friendly_name", "Desconocido")
            virtual = conf.get("is_virtual", is_virtual_device(friendly_name))
            
            result.append({
                "friendly_name": friendly_name,
                "device_path": dp,
                "port": conf.get("port", 0),
                "resolution": conf.get("resolution", "720p"),
                "fps": conf.get("fps", 30),
                "bitrate": conf.get("bitrate", 3000),
                "protocol": conf.get("protocol", "srt"),
                "encoder": conf.get("_actual_encoder", conf.get("encoder", "auto")),
                "srt_latency": conf.get("srt_latency", 120),
                "srt_passphrase": conf.get("srt_passphrase", ""),
                "zerolatency": conf.get("zerolatency", True),
                "auto_start": conf.get("auto_start", True),
                "is_virtual": virtual,
                "is_connected": proc.is_connected,
                "url": conf.get("_url", ""),
                
                "status": {
                    "state": proc.state,
                    "pid": proc.process.pid if proc.is_alive else None,
                    "uptime_seconds": uptime,
                    "error_count": proc.error_count,
                    "current_fps": proc.current_fps,
                    "current_bitrate_kbps": proc.current_bitrate_kbps,
                    "current_speed": proc.current_speed,
                    "using_fallback_cpu": proc.using_fallback_cpu
                }
            })
        return result

stream_manager = StreamManager()

async def sync_streams_with_hardware():
    await stream_manager.sync_streams_with_hardware()

def get_all_stream_statuses() -> list:
    return stream_manager.get_all_stream_statuses()
