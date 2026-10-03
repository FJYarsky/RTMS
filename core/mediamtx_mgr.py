# ==============================================================================
# RTMS — Real-Time Multicam System
# Administrador de ciclo de vida del Media Server local (MediaMTX).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Administrador del ciclo de vida, configuración dinámica y telemetría de MediaMTX."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from typing import Any, Dict, List, Optional

from core.power_mgr import get_base_dir

logger = logging.getLogger("rtms.mediamtx")

DEFAULT_MEDIAMTX_SRT_PORT = 8890
DEFAULT_MEDIAMTX_API_PORT = 9997
DEFAULT_MEDIAMTX_WEBRTC_PORT = 8889
# CREATE_NO_WINDOW (0x08000000) | HIGH_PRIORITY_CLASS (0x00000080)
_WIN_FLAGS = (0x08000000 | 0x00000080) if sys.platform == "win32" else 0


def clean_camera_id(cam_id: Any) -> str:
    """Sanitiza el ID de cámara para rutas seguras en MediaMTX y URLs."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(cam_id)) if cam_id else ""


class MediaMTXManager:
    """
    Gestor del ciclo de vida del subproceso MediaMTX.
    Controla el arranque determinista, configuración dinámica en caliente,
    monitoreo de salud vía API interna y reinicio ante fallos.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or get_base_dir()
        self.bin_path = os.path.join(self.base_dir, "bin", "mediamtx.exe")
        self.config_template_path = os.path.join(self.base_dir, "config", "mediamtx.example.yml")
        self.config_active_path = os.path.join(self.base_dir, "config", "mediamtx.yml")

        self.srt_port = DEFAULT_MEDIAMTX_SRT_PORT
        self.webrtc_port = DEFAULT_MEDIAMTX_WEBRTC_PORT
        try:
            from core.config_mgr import load_config

            cfg = load_config()
            self.srt_port = int(cfg.get("mediamtx_srt_port", DEFAULT_MEDIAMTX_SRT_PORT))
            self.webrtc_port = int(cfg.get("mediamtx_webrtc_port", DEFAULT_MEDIAMTX_WEBRTC_PORT))
        except Exception:
            pass
        self.api_port = DEFAULT_MEDIAMTX_API_PORT

        self.log_path = os.path.join(self.base_dir, "config", "mediamtx.log")
        self._log_file: Optional[Any] = None
        self._process: Optional[subprocess.Popen] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._inactivity_task: Optional[asyncio.Task] = None
        self._active_srt_streams: set = set()
        self._last_activity_time: float = 0.0
        self._grace_period_seconds: float = 20.0
        self._is_shutting_down = False
        self._lock = asyncio.Lock()

    def get_srt_port(self) -> int:
        """Retorna el puerto central SRT configurado para MediaMTX."""
        return self.srt_port

    def get_webrtc_port(self) -> int:
        """Retorna el puerto central WebRTC / WHEP configurado para MediaMTX."""
        return self.webrtc_port

    def get_api_port(self) -> int:
        """Retorna el puerto de la API interna de MediaMTX."""
        return self.api_port

    def ensure_config_exists(self) -> str:
        """Verifica o genera la configuración activa de MediaMTX y retorna su ruta."""
        if not os.path.exists(self.config_active_path):
            return self.generate_config()
        return self.config_active_path

    def get_bin_path(self) -> str:
        """Retorna la ruta al ejecutable de MediaMTX, con fallback al PATH del sistema."""
        if os.path.exists(self.bin_path):
            return self.bin_path
        sys_bin = shutil.which("mediamtx")
        if sys_bin:
            return sys_bin
        return self.bin_path

    def is_binary_available(self) -> bool:
        """Verifica si el binario de MediaMTX se encuentra disponible físicamente."""
        return os.path.exists(self.get_bin_path())

    def generate_config(self, srt_port: Optional[int] = None) -> str:
        """
        Genera el archivo config/mediamtx.yml en caliente con los puertos configurados.
        Garantiza que el servidor no active protocolos no requeridos.
        Por seguridad estricta (CWE-312), las frases de paso de cámaras no se almacenan
        en texto plano en disco, sino que se inyectan en memoria a través de la API de MediaMTX.
        """
        if srt_port:
            self.srt_port = srt_port

        os.makedirs(os.path.dirname(self.config_active_path), exist_ok=True)

        # Detectar IP local para candidatos ICE de WebRTC en host multi-NIC (v2.8.2)
        local_ip = "127.0.0.1"
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.2)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
        except Exception:
            try:
                import socket

                local_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                local_ip = "127.0.0.1"

        config_content = (
            "# RTMS Dynamic MediaMTX Configuration — Low Latency Calibrated\n"
            "writeQueueSize: 128\n"
            "udpMaxPayloadSize: 1472\n\n"
            "api: yes\n"
            f"apiAddress: 127.0.0.1:{self.api_port}\n\n"
            "rtsp: no\n"
            "rtmp: no\n"
            "hls: no\n\n"
            "webrtc: yes\n"
            f"webrtcAddress: :{self.webrtc_port}\n"
            f'webrtcAdditionalHosts: ["{local_ip}"]\n'
            "webrtcEncryption: no\n"
            "webrtcLocalUDPAddress: :8189\n"
            'webrtcAllowOrigin: "*"\n\n'
            "srt: yes\n"
            f"srtAddress: :{self.srt_port}\n\n"
            "paths:\n"
            "  all_others:\n"
            "    overridePublisher: yes\n"
        )

        tmp_path = self.config_active_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        try:
            os.replace(tmp_path, self.config_active_path)
        except OSError:
            shutil.move(tmp_path, self.config_active_path)

        logger.info(f"Configuración de MediaMTX generada en {self.config_active_path} (SRT :{self.srt_port})")
        return self.config_active_path

    async def start(self, srt_port: Optional[int] = None) -> bool:
        """
        Inicia el subproceso MediaMTX y espera a que su API interna responda salud.
        Retorna True si arrancó y está listo para recibir ingesta.
        """
        async with self._lock:
            if self.is_running():
                logger.debug("MediaMTX ya se encuentra en ejecución.")
                return True

            if not self.is_binary_available():
                logger.error(
                    f"No se encontró el ejecutable MediaMTX en '{self.bin_path}'. "
                    "Ejecute 'powershell -ExecutionPolicy Bypass -File scripts/setup_binaries.ps1' para instalarlo."
                )
                return False

            self._is_shutting_down = False
            config_file = self.generate_config(srt_port=srt_port)
            bin_file = self.get_bin_path()

            logger.info(f"Lanzando MediaMTX daemon [{bin_file}]...")
            try:
                # Rotar / limpiar log de MediaMTX si excede 5MB
                try:
                    if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 5 * 1024 * 1024:
                        with open(self.log_path, "w", encoding="utf-8") as lf:
                            lf.truncate(0)
                except Exception:
                    pass

                try:
                    os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                    self._log_file = open(self.log_path, "a", encoding="utf-8")
                except Exception as ex_lf:
                    logger.debug(f"Aviso abriendo logfile para MediaMTX: {ex_lf}")
                    self._log_file = None

                out_target = self._log_file if self._log_file is not None else subprocess.DEVNULL
                self._process = subprocess.Popen(
                    [bin_file, config_file],
                    stdout=out_target,
                    stderr=out_target,
                    creationflags=_WIN_FLAGS,
                )

                if self._process and isinstance(getattr(self._process, "pid", None), int):
                    try:
                        from core.process_optimizer import (
                            HIGH_PRIORITY_CLASS,
                            elevate_process_priority,
                            get_pcore_affinity_mask,
                        )

                        elevate_process_priority(
                            self._process.pid, HIGH_PRIORITY_CLASS, core_mask=get_pcore_affinity_mask()
                        )
                    except Exception as opt_err:
                        logger.debug(f"Aviso elevando prioridad de MediaMTX: {opt_err}")

                # Registrar en Job Object de Windows si está disponible
                try:
                    from core.job_object import job_object_mgr

                    job_object_mgr.assign_process(self._process)
                except Exception as e:
                    logger.debug(f"Asignación de MediaMTX a Job Object omitida o fallida: {e}")

                # Esperar activamente a que la API responda salud
                ready = await self._wait_for_api_ready(timeout=5.0)
                if not ready:
                    logger.error("MediaMTX no respondió en su endpoint de API dentro del tiempo límite.")
                    self.stop()
                    return False

                logger.info(f"MediaMTX iniciado exitosamente (SRT puerto {self.srt_port}, API {self.api_port}).")

                # Sincronizar en memoria las rutas de cámaras protegidas vía API local (CWE-312)
                try:
                    await self.sync_paths_api()
                except Exception as ex:
                    logger.debug(f"Aviso en sincronización inicial de rutas MediaMTX: {ex}")

                # Registrar tiempo de actividad inicial
                try:
                    self._last_activity_time = asyncio.get_event_loop().time()
                except RuntimeError:
                    import time

                    self._last_activity_time = time.time()

                # Iniciar tarea de supervisión continua
                if not self._watchdog_task or self._watchdog_task.done():
                    self._watchdog_task = asyncio.create_task(self._supervise_loop())

                # Iniciar tarea de apagado por inactividad (período de gracia de 20s)
                if not self._inactivity_task or self._inactivity_task.done():
                    self._inactivity_task = asyncio.create_task(self._inactivity_watchdog_loop())

                return True
            except Exception as e:
                logger.exception(f"Error crítico iniciando subproceso MediaMTX: {e}")
                self.stop()
                return False

    async def _wait_for_api_ready(self, timeout: float = 5.0) -> bool:
        """Realiza sondeo asíncrono a la API de MediaMTX hasta recibir HTTP 200."""
        url = f"http://127.0.0.1:{self.api_port}/v3/paths/list"
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:

                def check_sync():
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=0.5) as resp:
                        return resp.status == 200

                ready = await asyncio.to_thread(check_sync)
                if ready:
                    return True
            except Exception:
                await asyncio.sleep(0.15)
        return False

    def is_running(self) -> bool:
        """Verifica si el subproceso MediaMTX está activo y respondiendo."""
        if not self._process:
            return False
        return self._process.poll() is None

    async def _supervise_loop(self):
        """Supervisa el proceso de MediaMTX cada 3 segundos y lo reinicia si cae involuntariamente."""
        while not self._is_shutting_down:
            try:
                await asyncio.sleep(3.0)
                if self._is_shutting_down:
                    break
                if not self.is_running():
                    if self._is_shutting_down:
                        break
                    logger.warning("Subproceso MediaMTX finalizado inesperadamente. Reiniciando...")
                    await self.start(self.srt_port)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en supervisor de MediaMTX: {e}")

    def stop(self):
        """Detiene el subproceso MediaMTX y cancela el supervisor."""
        self._is_shutting_down = True
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self._inactivity_task and not self._inactivity_task.done():
            self._inactivity_task.cancel()
            self._inactivity_task = None

        if self._process:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=1.0)
            except Exception as e:
                logger.debug(f"Excepción al detener MediaMTX: {e}")
            finally:
                self._process = None

        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

        logger.info("MediaMTX detenido limpiamente.")

    def register_srt_stream(self, device_path: str):
        """Registra una cámara activa transmitiendo en protocolo SRT."""
        self._active_srt_streams.add(device_path)
        try:
            self._last_activity_time = asyncio.get_event_loop().time()
        except RuntimeError:
            import time

            self._last_activity_time = time.time()
        logger.debug(f"[MediaMTX] Flujo SRT registrado: {device_path} (Total activos: {len(self._active_srt_streams)})")

    def unregister_srt_stream(self, device_path: str):
        """Desregistra una cámara que cesó de transmitir en protocolo SRT."""
        self._active_srt_streams.discard(device_path)
        try:
            self._last_activity_time = asyncio.get_event_loop().time()
        except RuntimeError:
            import time

            self._last_activity_time = time.time()
        logger.debug(f"[MediaMTX] Flujo SRT desregistrado: {device_path} (Restantes: {len(self._active_srt_streams)})")

    def register_webrtc_activity(self):
        """Registra actividad o solicitud de señalización WebRTC (WHEP)."""
        try:
            self._last_activity_time = asyncio.get_event_loop().time()
        except RuntimeError:
            import time

            self._last_activity_time = time.time()

    async def ensure_started(self, srt_port: Optional[int] = None) -> bool:
        """Inicia MediaMTX bajo demanda si no se encuentra en ejecución."""
        self.register_webrtc_activity()
        if not self.is_running():
            return await self.start(srt_port=srt_port)
        return True

    async def _inactivity_watchdog_loop(self):
        """
        Supervisa la inactividad de MediaMTX. Si no hay streams SRT ni visores WebRTC
        activos durante 20 segundos continuos, apaga el servidor para liberar RAM y cerrar puertos.
        """
        while not self._is_shutting_down:
            try:
                await asyncio.sleep(2.0)
                if self._is_shutting_down or not self.is_running():
                    break

                # Si hay flujos SRT registrados localmente, no apagar
                if self._active_srt_streams:
                    continue

                # Comprobar período de gracia de 20 segundos
                loop_time = asyncio.get_event_loop().time()
                if (loop_time - self._last_activity_time) >= self._grace_period_seconds:
                    logger.info(
                        f"MediaMTX inactivo durante {int(self._grace_period_seconds)}s (sin flujos SRT ni visores WebRTC). "
                        "Apagando proceso bajo demanda para liberar memoria..."
                    )
                    self.stop()
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Aviso en supervisor de inactividad MediaMTX: {e}")

    async def restart(self, new_srt_port: Optional[int] = None) -> bool:
        """Reinicia el servidor MediaMTX con un nuevo puerto SRT si se especifica."""
        self.stop()
        await asyncio.sleep(0.5)
        return await self.start(srt_port=new_srt_port)

    async def get_paths(self) -> List[Dict[str, Any]]:
        """Obtiene la lista de rutas activas y lectores conectados a MediaMTX."""
        if not self.is_running():
            return []
        url = f"http://127.0.0.1:{self.api_port}/v3/paths/list"
        try:

            def fetch_sync():
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        return data.get("items", [])
                return []

            return await asyncio.to_thread(fetch_sync)
        except Exception as e:
            logger.debug(f"Error consultando rutas activas en MediaMTX: {e}")
            return []

    async def sync_paths_api(self) -> None:
        """
        Sincroniza en memoria las rutas de cámaras protegidas con la API de control de MediaMTX.
        Evita el almacenamiento de credenciales en texto plano en disco (CWE-312).
        """
        if not self.is_running():
            return

        def _do_sync():
            cameras = {}
            try:
                from core.repository import config_repository

                cameras = config_repository.get_all_cameras_sync()
            except Exception:
                pass

            if not cameras:
                try:
                    from core.config_mgr import load_config

                    cfg = load_config()
                    cameras = cfg.get("cameras", {})
                except Exception:
                    pass

            from core.secrets_mgr import unprotect_secret

            for cam in cameras.values():
                c_id = cam.get("id") or cam.get("camera_id") or cam.get("port")
                clean_id = clean_camera_id(c_id)
                raw_pass = cam.get("srt_passphrase", "")
                plain_pass = unprotect_secret(raw_pass) if raw_pass else ""
                self._apply_path_api_sync(clean_id, plain_pass)

        await asyncio.to_thread(_do_sync)

    async def sync_path_api(self, clean_id: str, plain_pass: str) -> None:
        """Sincroniza asíncronamente una ruta individual protegida en MediaMTX."""
        if not self.is_running() or not clean_id:
            return
        await asyncio.to_thread(self._apply_path_api_sync, clean_id, plain_pass)

    def _apply_path_api_sync(self, clean_id: str, plain_pass: str) -> None:
        """Configura o actualiza una ruta en MediaMTX vía su API REST local."""
        import urllib.error

        if not clean_id or clean_id == "all_others":
            return

        api_base = f"http://127.0.0.1:{self.api_port}/v3/config/paths"
        if plain_pass:
            add_url = f"{api_base}/add/{clean_id}"
            body = json.dumps({"srtReadPassphrase": plain_pass}).encode("utf-8")
            req = urllib.request.Request(
                add_url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status in (200, 201):
                        return
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    patch_url = f"{api_base}/patch/{clean_id}"
                    preq = urllib.request.Request(
                        patch_url, data=body, headers={"Content-Type": "application/json"}, method="PATCH"
                    )
                    try:
                        with urllib.request.urlopen(preq, timeout=1.0):
                            pass
                    except Exception as patch_err:
                        logger.debug(f"Aviso actualizando ruta {clean_id} en MediaMTX: {patch_err}")
                else:
                    logger.debug(f"Aviso agregando ruta {clean_id} a MediaMTX: {e}")
            except Exception as e:
                logger.debug(f"Aviso comunicando con API de MediaMTX para ruta {clean_id}: {e}")
        else:
            del_url = f"{api_base}/delete/{clean_id}"
            req = urllib.request.Request(del_url, method="DELETE")
            try:
                with urllib.request.urlopen(req, timeout=1.0):
                    pass
            except Exception:
                pass


# Instancia singleton global
mediamtx_manager = MediaMTXManager()
