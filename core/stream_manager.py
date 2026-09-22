# ==============================================================================
# RTMS — Real-Time Multicam System
# Orquestación, supervisión y ciclo de vida de procesos de transmisión.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Gestor de flujos de transmisión FFmpeg, supervisión watchdog y balanceo de codificadores."""

import asyncio
import logging
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from core.command_builder import build_ffmpeg_command
from core.config_mgr import get_or_allocate_camera_config
from core.hardware import _FFMPEG_BIN, get_directshow_devices, hardware_detector, has_ffmpeg_binary
from core.mediamtx_mgr import clean_camera_id, mediamtx_manager
from core.port_mgr import port_manager
from core.sanitizer import sanitize_command_for_log, sanitize_log_line, sanitize_url
from core.stream_proc import ErrorCategory, State, StreamProc

logger = logging.getLogger("rtms.stream_manager")

# CREATE_NO_WINDOW (0x08000000) | ABOVE_NORMAL_PRIORITY_CLASS (0x00008000) para FFmpeg prioritario
_WIN_FLAGS = (0x08000000 | 0x00008000) if sys.platform == "win32" else 0


class StreamManager:
    """Orquestador central para la inicialización, monitoreo y recuperación de procesos de streaming."""

    WATCHDOG_INTERVAL = 2  # Intervalo de evaluación ágil no bloqueante
    MAX_ERRORS = 5
    STABILITY_THRESHOLD_SECONDS = 60

    def __init__(self):
        self._procs: Dict[str, StreamProc] = {}
        self._watchdog_task: Optional[asyncio.Task] = None
        self._handling_device_lost: Set[str] = set()

    def get_proc(self, device_path: str) -> StreamProc:
        if device_path not in self._procs:
            self._procs[device_path] = StreamProc(device_path)
        return self._procs[device_path]

    async def detect_best_encoder(self, proc: Optional[StreamProc] = None) -> str:
        """
        Detecta el mejor codificador por hardware disponible consultando la caché global singleton.
        Evita lanzar subprocesos redundantes de prueba en cada stream mediante caché compartida.
        """
        if proc and proc.per_stream_encoder:
            return proc.per_stream_encoder

        best = await hardware_detector.get_best_encoder()
        if proc:
            proc.per_stream_encoder = best
        return best

    async def build_command(self, cfg: Dict[str, Any], force_cpu: bool = False, proc: Optional[StreamProc] = None):
        """Construye el comando invocando el constructor modular de comandos."""
        return await build_ffmpeg_command(
            cfg, force_cpu=force_cpu, proc=proc, best_encoder_getter=self.detect_best_encoder
        )

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
        proc.clear_failure()
        proc.zero_fps_since = None
        proc.using_fallback_cpu = force_cpu

        # Bloqueo por fallo de descifrado de credencial
        if proc.config.get("decryption_failed"):
            logger.error(f"[{proc.device_path}] Imposible iniciar transmisión: Falló el descifrado seguro DPAPI.")
            proc.transition_to(State.MANUAL_INTERVENTION_REQUIRED)
            proc.last_error_category = ErrorCategory.AUTHENTICATION
            proc.log("ERROR CRÍTICO: Falló el descifrado de la credencial SRT. Intervención manual requerida.")
            return

        # Revalidación de puerto en tiempo de inicio para prevenir colisiones
        cfg_port = proc.config.get("port")
        if cfg_port and not port_manager.revalidate_port(int(cfg_port)):
            logger.warning(
                f"Puerto {cfg_port} ocupado en el sistema antes de iniciar {proc.device_path}. Reasignando..."
            )
            new_port = port_manager.reallocate_if_collided(int(cfg_port))
            proc.config["port"] = new_port
            from core.config_mgr import load_config, save_config

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
                creationflags=_WIN_FLAGS,
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

        try:
            from core.job_object import job_object_mgr

            if process.pid:
                job_object_mgr.assign_process(process.pid)
        except Exception as e:
            logger.debug(f"Asignación a Job Object omitida o fallida: {e}")

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

        # Cancelación y limpieza de la tarea asíncrona de recuperación
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
                    proc.process.stdin.write(b"q\n")
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
        proc.zero_fps_since = None
        proc.log("Stream detenido limpiamente.")

    async def remove_stream(self, device_path: str) -> bool:
        """Detiene la transmisión, libera el puerto y elimina la cámara de forma permanente."""
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

        # Invalidar tickets de preview asociados a esta cámara
        try:
            from api.deps import preview_ticket_mgr

            preview_ticket_mgr.invalidate_for_device(device_path)
        except Exception:
            pass

        from core.config_mgr import remove_camera_config

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
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except (asyncio.CancelledError, Exception):
                pass
            self._watchdog_task = None

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

    async def _handle_device_lost(self, device_path: str):
        """Maneja la desconexión física o apagado (F5/USB) de un dispositivo de captura con protección contra llamadas concurrentes redundantes."""
        if device_path in self._handling_device_lost:
            return
        self._handling_device_lost.add(device_path)
        try:
            proc = self.get_proc(device_path)
            devices = await get_directshow_devices()
            detected_paths = {d["device_path"] for d in devices}
            if device_path not in detected_paths:
                logger.warning(f"Cámara {device_path} desconectada físicamente (hotplug/F5). Marcando DISCONNECTED.")
                proc.is_connected = False
                proc.transition_to(State.DISCONNECTED)
                proc.error_count = 0
                proc.manual_intervention_required = False
                proc.zero_fps_since = None
                if proc.is_alive:
                    await self.stop_stream(device_path, timeout=1.0)
        finally:
            self._handling_device_lost.discard(device_path)

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
                        if uptime >= self.STABILITY_THRESHOLD_SECONDS and (
                            proc.error_count > 0 or proc.permanent_failure
                        ):
                            logger.info(f"Flujo {dp} estable por {int(uptime)}s. Reseteando contadores de error.")
                            proc.clear_failure()

                        # Detección de congelamiento por desconexión física de hardware (0 FPS sostenido)
                        if uptime >= 8.0 and proc.current_fps == 0.0:
                            if proc.zero_fps_since is None:
                                proc.zero_fps_since = now
                            elif (now - proc.zero_fps_since).total_seconds() >= 8.0:
                                devices = await get_directshow_devices()
                                detected_paths = {d["device_path"] for d in devices}
                                if dp not in detected_paths:
                                    logger.warning(
                                        f"Cámara {dp} sin cuadros (0 fps) y no encontrada en DirectShow. Desconectando..."
                                    )
                                    proc.is_connected = False
                                    proc.transition_to(State.DISCONNECTED)
                                    proc.zero_fps_since = None
                                    proc.error_count = 0
                                    proc.manual_intervention_required = False
                                    asyncio.create_task(self.stop_stream(dp, timeout=1.0))
                                    continue
                        else:
                            proc.zero_fps_since = None
                        continue

                    # 2. Detección de caída de flujo
                    if not proc.is_alive and proc.state == State.RUNNING:
                        # Si el fallo fue originado por desconexión física de hardware
                        if proc.last_error_category == ErrorCategory.DEVICE:
                            devices = await get_directshow_devices()
                            detected_paths = {d["device_path"] for d in devices}
                            if dp not in detected_paths:
                                proc.is_connected = False
                                proc.transition_to(State.DISCONNECTED)
                                proc.error_count = 0
                                proc.next_retry_at = None
                                proc.manual_intervention_required = False
                                logger.info(f"Cámara {dp} no disponible físicamente. Pausada en DISCONNECTED.")
                                continue

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
                                logger.info(
                                    f"Watchdog recuperando {dp} (intento {proc.error_count}/{self.MAX_ERRORS})..."
                                )
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
                                logger.error(
                                    f"Flujo {dp} superó el límite de {self.MAX_ERRORS} errores. Pausado esperando intervención manual."
                                )
                                proc.log(
                                    f"CRÍTICO: Superado límite de {self.MAX_ERRORS} errores consecutivos. Pausado esperando intervención manual."
                                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en Watchdog: {e}")

    async def reallocate_if_collided(self, proc: StreamProc) -> int:
        """Reasigna un puerto libre ante colisión y actualiza la configuración."""
        proc.last_error_category = ErrorCategory.PORT_COLLISION
        cfg_port = proc.config.get("port", 9000)
        new_port = port_manager.reallocate_if_collided(int(cfg_port))
        proc.config["port"] = new_port
        from core.config_mgr import load_config, save_config

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
            "cannot find video device",
            "capture device was lost",
            "device removed",
            "error reading from input",
            "input/output error",
            "i/o error",
            "error while opening encoder",
            "bind failed",
            "address already in use",
        ]

        stats_pattern = re.compile(r"fps=\s*([0-9.]+).*bitrate=\s*([0-9.]+)kbits/s.*speed=\s*([0-9.x]+)")

        if process.stderr is None:
            return

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

                # Detección de colisión de socket en tiempo de ejecución
                if "bind failed" in line_lower or "address already in use" in line_lower:
                    logger.warning(
                        f"[{device_path}] Colisión de socket detectada en FFmpeg: {clean_line}. Reasignando puerto..."
                    )
                    await self.reallocate_if_collided(proc)

                if any(pat in line_lower for pat in FATAL_PATTERNS):
                    logger.warning(f"[{device_path}] Error en FFmpeg: {clean_line}")

                    # Clasificación de categoría de error según diagnóstico de FFmpeg
                    is_output_or_net = any(
                        term in line_lower
                        for term in [
                            "out#",
                            "error opening output",
                            "connection to srt",
                            "[srt @",
                            "connection refused",
                            "bind failed",
                            "badsecret",
                            "incorrect passphrase",
                            "broken pipe",
                            "destination unreachable",
                            "connection reset",
                        ]
                    )

                    is_dshow_input = any(
                        term in line_lower
                        for term in [
                            "could not find video device",
                            "cannot find video device",
                            "device not found",
                            "dshow: could not",
                            "capture device was lost",
                            "device removed",
                            "error reading from input",
                        ]
                    ) or (("input/output error" in line_lower or "i/o error" in line_lower) and not is_output_or_net)

                    if is_dshow_input:
                        proc.last_error_category = ErrorCategory.DEVICE
                        asyncio.create_task(self._handle_device_lost(device_path))
                    elif "error while opening encoder" in line_lower:
                        proc.last_error_category = ErrorCategory.ENCODER
                    elif is_output_or_net:
                        proc.last_error_category = ErrorCategory.NETWORK
                    else:
                        proc.last_error_category = ErrorCategory.PROCESS

                    if "error while opening encoder" in line_lower and not proc.using_fallback_cpu:
                        asyncio.create_task(self._fallback_to_cpu(device_path))
                        return

                    if proc.state == State.RUNNING:
                        if proc.last_error_category == ErrorCategory.DEVICE:
                            # Se delega a _handle_device_lost para verificar si el hardware desapareció sin quemar reintentos
                            pass
                        else:
                            proc.transition_to(State.ERROR)
                            proc.error_count += 1
                            backoff = min(5 * (2 ** max(0, proc.error_count - 1)), 60)
                            proc.next_retry_at = datetime.now() + timedelta(seconds=backoff)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error leyendo logs de {device_path}: {e}")

    async def start_periodic_hardware_sync(self, interval: int = 5):
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
            try:
                from core.task_registry import task_registry

                self._watchdog_task = task_registry.create_task(self.watchdog(), name="stream_manager_watchdog")
            except Exception:
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

        # 2. Registrar y actualizar dispositivos presentes (omitiendo dispositivos en ignored_devices)
        from core.config_mgr import is_device_ignored

        for d in devices:
            dp = d["device_path"]
            if is_device_ignored(dp):
                continue
            proc = self.get_proc(dp)
            was_disconnected = not proc.is_connected or proc.state == State.DISCONNECTED
            proc.config = get_or_allocate_camera_config(dp, d["friendly_name"])
            proc.is_connected = True

            # Si la cámara se reconectó o salió del estado desconectado
            if was_disconnected:
                proc.clear_failure()
                proc.zero_fps_since = None
                if proc.config.get("auto_start", False) and not proc._stop_evt.is_set():
                    logger.info(f"Cámara {dp} reconectada físicamente. Restaurando transmisión...")
                    proc.log("Cámara reconectada. Restaurando transmisión automáticamente...")
                    asyncio.create_task(self.start_stream(dp))
                else:
                    proc.transition_to(State.STOPPED)
                    proc.log("Cámara detectada y conectada. Lista para iniciar.")
            elif proc.config.get("auto_start", False) and proc.state == State.STOPPED and not proc._stop_evt.is_set():
                asyncio.create_task(self.start_stream(dp))

        # Sincronizar en memoria las rutas con MediaMTX API
        try:
            from core.mediamtx_mgr import mediamtx_manager

            await mediamtx_manager.sync_paths_api()
        except Exception as e:
            logger.debug(f"Aviso sincronizando rutas en MediaMTX tras escaneo de hardware: {e}")

    @property
    def has_active_streams(self) -> bool:
        """Indica si existe al menos un proceso de transmisión activo en ejecución."""
        return any(proc.is_alive for proc in self._procs.values())

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        statuses = []
        mediamtx_port = mediamtx_manager.get_srt_port()

        for dp, proc in self._procs.items():
            cfg = proc.config or {}
            raw_pass = cfg.get("srt_passphrase", "")
            raw_url = cfg.get("_url", "")
            cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{cfg.get('port', 9000)}"
            clean_cam_id = clean_camera_id(cam_id)
            statuses.append(
                {
                    "id": cfg.get("id", ""),
                    "clean_cam_id": clean_cam_id,
                    "device_path": dp,
                    "friendly_name": cfg.get("friendly_name", dp),
                    "resolution": cfg.get("resolution", "720p"),
                    "fps": cfg.get("fps", 30),
                    "bitrate": cfg.get("bitrate", 3000),
                    "protocol": cfg.get("protocol", "srt"),
                    "udp_mode": cfg.get("udp_mode", "multicast"),
                    "port": cfg.get("port", 9000),
                    "mediamtx_port": mediamtx_port,
                    "encoder": cfg.get("encoder", "auto"),
                    "actual_encoder": cfg.get("_actual_encoder", proc.per_stream_encoder or "auto"),
                    "srt_latency": cfg.get("srt_latency", 120),
                    "srt_passphrase": "••••••••" if raw_pass else "",
                    "has_passphrase": bool(raw_pass),
                    "decryption_failed": bool(cfg.get("decryption_failed", False)),
                    "url": sanitize_url(raw_url),
                    "auto_start": cfg.get("auto_start", False),
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
                        "uptime_seconds": (datetime.now() - proc.started_at).total_seconds()
                        if proc.is_alive and proc.started_at
                        else None,
                    },
                }
            )
        return statuses


# Instancia global única
stream_manager = StreamManager()
