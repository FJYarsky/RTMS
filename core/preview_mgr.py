# ==============================================================================
# RTMS — Real-Time Multicam System
# Gestor de previsualización de video en vivo (snapshots MJPEG y visor FFplay).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import os
import sys
import re
import urllib.parse
import shutil
import asyncio
import logging
import subprocess
from typing import Optional, Dict, AsyncGenerator, Set

from core.sanitizer import sanitize_url
from .hardware import get_ffmpeg_bin, has_ffmpeg_binary, _WIN_FLAGS

logger = logging.getLogger("rtms.preview")

def get_ffplay_bin() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    bundled = os.path.join(base_dir, "bin", "ffplay.exe")
    if os.path.exists(bundled):
        return bundled
    system_play = shutil.which("ffplay")
    if system_play:
        return system_play
    return bundled

class PreviewManager:
    """
    Gestor de Vista Previa de video On-Demand con control de concurrencia (N8, P1-10).
    Garantiza 0% de uso de CPU y GPU cuando no está activo.
    Completamente aislado del proceso principal de transmisión.
    """
    MAX_CONCURRENT_PREVIEWS = 3
    MAX_JPEG_BUFFER = 4 * 1024 * 1024  # 4 MB límite de seguridad (N14)

    def __init__(self):
        self._active_ffplay: Dict[str, subprocess.Popen] = {}
        self._preview_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PREVIEWS)
        self._active_camera_previews: Set[str] = set()
        self._concurrency_lock = asyncio.Lock()

    @staticmethod
    def has_ffmpeg_binary() -> bool:
        """Verifica si el binario de FFmpeg está disponible (N3)."""
        return has_ffmpeg_binary()

    async def acquire_slot(self, identifier: str) -> bool:
        """Adquiere un slot de visualización concurrente (máx 3 globales, 1 por cámara) (P1-10)."""
        async with self._concurrency_lock:
            if identifier in self._active_camera_previews:
                return False
            try:
                # Usar wait_for con timeout 0 para intento no bloqueante
                await asyncio.wait_for(self._preview_semaphore.acquire(), timeout=0.01)
                self._active_camera_previews.add(identifier)
                return True
            except asyncio.TimeoutError:
                return False

    async def release_slot(self, identifier: str):
        """Libera el slot de visualización ocupado."""
        async with self._concurrency_lock:
            if identifier in self._active_camera_previews:
                self._active_camera_previews.remove(identifier)
                self._preview_semaphore.release()

    def _reap_dead_processes(self):
        """Limpia referencias a procesos FFplay que ya terminaron para evitar acumulación de handles muertos."""
        dead_keys = [url for url, proc in self._active_ffplay.items() if proc.poll() is not None]
        for key in dead_keys:
            self._active_ffplay.pop(key, None)

    def launch_ffplay(self, url: str, title: str = "RTMS Preview", is_dshow: bool = False) -> bool:
        self._reap_dead_processes()
        ffplay_bin = get_ffplay_bin()
        if not os.path.exists(ffplay_bin) and not shutil.which("ffplay"):
            logger.error(f"Binario FFplay no encontrado en {ffplay_bin}")
            return False

        # Sanitizar título de ventana para prevenir inyección de caracteres o banderas
        safe_title = re.sub(r'[^a-zA-Z0-9\s\-_\.\(\):áéíóúÁÉÍÓÚñÑ—]', '', str(title))[:120].strip() or "RTMS Preview"

        # Cerrar instancia previa para esta URL si ya existe
        if url in self._active_ffplay:
            prev = self._active_ffplay.pop(url, None)
            if prev and prev.poll() is None:
                try:
                    prev.terminate()
                    try:
                        prev.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        prev.kill()
                except Exception:
                    pass

        if is_dshow:
            clean_device = re.sub(r'[\r\n\t\0"]', '', str(url)).strip()
            if not clean_device or clean_device.startswith("-"):
                logger.warning(f"Dispositivo DirectShow no válido para FFplay: {url}")
                return False
            escaped = clean_device.replace(":", "\\:")
            cmd = [
                ffplay_bin,
                "-window_title", safe_title,
                "-f", "dshow",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-framedrop",
                "-x", "854",
                "-y", "480",
                "-i", f"video={escaped}"
            ]
        else:
            clean_url = str(url).strip()
            if not clean_url or clean_url.startswith("-") or any(c in clean_url for c in "\r\n\t\0"):
                logger.warning(f"URL no válida para FFplay: {url}")
                return False
            parsed = urllib.parse.urlparse(clean_url)
            if parsed.scheme not in ("srt", "udp", "http", "https"):
                logger.warning(f"Protocolo de URL no permitido para FFplay: {clean_url}")
                return False
            cmd = [
                ffplay_bin,
                "-window_title", safe_title,
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-framedrop",
                "-x", "854",
                "-y", "480",
                "-i", clean_url
            ]

        safe_url_log = sanitize_url(url)
        logger.info(f"Lanzando ventana nativa de vista previa con FFplay: {safe_url_log}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_WIN_FLAGS
            )
            self._active_ffplay[url] = proc
            return True
        except Exception as e:
            logger.error(f"Error al lanzar FFplay: {e}")
            return False

    async def get_snapshot_frame(self, device_path: str, timeout: float = 3.5) -> Optional[bytes]:
        """Captura un único cuadro JPEG directamente desde DirectShow para encuadre."""
        if not has_ffmpeg_binary():
            return None

        ffmpeg_bin = get_ffmpeg_bin()
        escaped_device = device_path.replace(":", "\\:")

        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-f", "dshow",
            "-i", f"video={escaped_device}",
            "-vframes", "1",
            "-s", "640x360",
            "-f", "image2",
            "-"
        ]

        p = None
        try:
            p = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=_WIN_FLAGS
            )
            stdout, _ = await asyncio.wait_for(p.communicate(), timeout=timeout)
            if p.returncode == 0 and stdout:
                return stdout
        except asyncio.TimeoutError:
            # Eliminar FFmpeg huérfano para no bloquear la cámara DirectShow (N4)
            logger.warning(f"Timeout al capturar snapshot de DirectShow para {device_path}. Terminando proceso forzosamente.")
            if p:
                try:
                    p.kill()
                    await asyncio.wait_for(p.wait(), timeout=1.0)
                except Exception:
                    pass
            return None
        except Exception as e:
            logger.debug(f"No se pudo capturar snapshot de DirectShow para {device_path}: {e}")
        return None

    async def generate_mjpeg_stream(
        self,
        input_source: str,
        is_dshow: bool = False,
        identifier: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Generador asíncrono que canaliza un flujo continuo de frames JPEG por HTTP (MJPEG).
        Al desconectarse el cliente, el bloque finally asegura la terminación inmediata del proceso FFmpeg.
        """
        if not has_ffmpeg_binary():
            return

        ffmpeg_bin = get_ffmpeg_bin()
        if is_dshow:
            escaped = input_source.replace(":", "\\:")
            cmd = [
                ffmpeg_bin,
                "-hide_banner",
                "-f", "dshow",
                "-i", f"video={escaped}",
                "-vf", "fps=10,scale=640:-1",
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-q:v", "5",
                "-"
            ]
        else:
            cmd = [
                ffmpeg_bin,
                "-hide_banner",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-i", input_source,
                "-vf", "fps=10,scale=640:-1",
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-q:v", "5",
                "-"
            ]

        proc = None
        safe_source_log = sanitize_url(input_source)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=_WIN_FLAGS
            )
            logger.info(f"Worker de vista previa iniciado para: {safe_source_log}")

            buffer = bytearray()
            while True:
                chunk = await proc.stdout.read(16384)
                if not chunk:
                    break
                buffer.extend(chunk)

                # Control defensivo de desbordamiento de memoria (N14)
                if len(buffer) > self.MAX_JPEG_BUFFER:
                    logger.warning(f"Buffer MJPEG superó {self.MAX_JPEG_BUFFER} bytes sin frame válido. Reiniciando buffer.")
                    buffer.clear()
                    continue

                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start == -1:
                        buffer.clear()
                        break
                    end = buffer.find(b"\xff\xd9", start)
                    if end == -1:
                        if start > 0:
                            del buffer[:start]
                        break

                    jpg_data = bytes(buffer[start:end+2])
                    del buffer[:end+2]

                    frame_block = (
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpg_data)).encode("ascii")
                        + b"\r\n\r\n"
                        + jpg_data
                        + b"\r\n"
                    )
                    yield frame_block

        except (asyncio.CancelledError, GeneratorExit):
            logger.info(f"Cliente de vista previa desconectado ({safe_source_log}). Liberando recursos.")
        except Exception as e:
            logger.debug(f"Aviso en worker de vista previa ({safe_source_log}): {e}")
        finally:
            if proc:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                    except Exception:
                        pass
                logger.info(f"Worker de vista previa detenido ({safe_source_log}). Consumo: 0.0%")
            if identifier:
                await self.release_slot(identifier)

    async def stop_all(self):
        """Detiene todas las ventanas de FFplay y libera todos los slots de previsualización (N5, P1-12)."""
        for proc in list(self._active_ffplay.values()):
            if proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=0.5)
                except Exception:
                    pass
        self._active_ffplay.clear()

        async with self._concurrency_lock:
            self._active_camera_previews.clear()
            self._preview_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PREVIEWS)

preview_manager = PreviewManager()
