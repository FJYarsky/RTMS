# ==============================================================================
# RTMS v2.2.1 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import os
import sys
import shutil
import asyncio
import logging
import subprocess
from typing import Optional, Dict, AsyncGenerator

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
    Gestor de Vista Previa de video On-Demand.
    Garantiza 0% de uso de CPU y GPU cuando no esta activo.
    Completamente aislado del proceso principal de transmision.
    """
    def __init__(self):
        self._active_ffplay: Dict[str, subprocess.Popen] = {}

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

        # Cerrar instancia previa para esta URL si ya existe
        if url in self._active_ffplay:
            prev = self._active_ffplay.pop(url, None)
            if prev and prev.poll() is None:
                try:
                    prev.terminate()
                except Exception:
                    pass

        if is_dshow:
            escaped = url.replace(":", "\\:")
            cmd = [
                ffplay_bin,
                "-window_title", title,
                "-f", "dshow",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-framedrop",
                "-x", "854",
                "-y", "480",
                "-i", f"video={escaped}"
            ]
        else:
            cmd = [
                ffplay_bin,
                "-window_title", title,
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-framedrop",
                "-x", "854",
                "-y", "480",
                url
            ]

        logger.info(f"Lanzando ventana nativa de vista previa con FFplay: {url}")
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

    async def get_snapshot_frame(self, device_path: str) -> Optional[bytes]:
        """Captura un unico cuadro JPEG directamente desde DirectShow para encuadre."""
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

        try:
            p = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=_WIN_FLAGS
            )
            stdout, _ = await asyncio.wait_for(p.communicate(), timeout=3.5)
            if p.returncode == 0 and stdout:
                return stdout
        except Exception as e:
            logger.debug(f"No se pudo capturar snapshot de DirectShow para {device_path}: {e}")
        return None

    async def generate_mjpeg_stream(self, input_source: str, is_dshow: bool = False) -> AsyncGenerator[bytes, None]:
        """
        Generador asincrono que canaliza un flujo continuo de frames JPEG por HTTP (MJPEG).
        Al desconectarse el cliente, el bloque finally asegura la terminacion inmediata del proceso FFmpeg.
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
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=_WIN_FLAGS
            )
            logger.info(f"Worker de vista previa iniciado para: {input_source}")

            buffer = bytearray()
            while True:
                chunk = await proc.stdout.read(16384)
                if not chunk:
                    break
                buffer.extend(chunk)

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
            logger.info(f"Cliente de vista previa desconectado ({input_source}). Liberando recursos.")
        except Exception as e:
            logger.debug(f"Aviso en worker de vista previa ({input_source}): {e}")
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
                logger.info(f"Worker de vista previa detenido ({input_source}). Consumo: 0.0%")

    def stop_all(self):
        for proc in self._active_ffplay.values():
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._active_ffplay.clear()

preview_manager = PreviewManager()
