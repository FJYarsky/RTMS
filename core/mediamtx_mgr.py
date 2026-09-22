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

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW


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
        try:
            from core.config_mgr import load_config

            cfg = load_config()
            self.srt_port = int(cfg.get("mediamtx_srt_port", DEFAULT_MEDIAMTX_SRT_PORT))
        except Exception:
            pass
        self.api_port = DEFAULT_MEDIAMTX_API_PORT
        self.webrtc_port = DEFAULT_MEDIAMTX_WEBRTC_PORT

        self._process: Optional[subprocess.Popen] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._is_shutting_down = False
        self._lock = asyncio.Lock()

    def get_srt_port(self) -> int:
        """Retorna el puerto central SRT configurado para MediaMTX."""
        return self.srt_port

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
        Garantiza que el servidor no active protocolos no requeridos y aplica srtReadPassphrase
        para cámaras con contraseña configurada.
        """
        if srt_port:
            self.srt_port = srt_port

        os.makedirs(os.path.dirname(self.config_active_path), exist_ok=True)

        paths_section = ""
        try:
            from core.secrets_mgr import unprotect_secret

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

            for cam in cameras.values():
                c_id = cam.get("id") or cam.get("camera_id") or cam.get("port")
                clean_id = clean_camera_id(c_id)
                raw_pass = cam.get("srt_passphrase", "")
                if clean_id and raw_pass:
                    plain_pass = unprotect_secret(raw_pass)
                    if plain_pass:
                        paths_section += f"  {clean_id}:\n    srtReadPassphrase: {plain_pass}\n"
        except Exception as ex:
            logger.debug(f"Aviso leyendo rutas de cámaras para MediaMTX: {ex}")

        config_content = (
            "# RTMS — Configuración Dinámica de MediaMTX (Autogenerada)\n"
            "api: yes\n"
            f"apiAddress: 127.0.0.1:{self.api_port}\n\n"
            "rtsp: no\n"
            "rtmp: no\n"
            "hls: no\n\n"
            "webrtc: yes\n"
            f"webrtcAddress: :{self.webrtc_port}\n\n"
            "srt: yes\n"
            f"srtAddress: :{self.srt_port}\n\n"
            "paths:\n"
            f"{paths_section}"
            "  all_others:\n"
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
                self._process = subprocess.Popen(
                    [bin_file, config_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=_WIN_FLAGS,
                )

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

                # Iniciar tarea de supervisión continua
                if not self._watchdog_task or self._watchdog_task.done():
                    self._watchdog_task = asyncio.create_task(self._supervise_loop())

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

        logger.info("MediaMTX detenido limpiamente.")

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


# Instancia singleton global
mediamtx_manager = MediaMTXManager()
