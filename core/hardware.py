# ==============================================================================
# RTMS — Real-Time Multicam System
# Detección y sondeo de dispositivos de captura de video.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Detección de dispositivos DirectShow y aceleración por hardware."""

import asyncio
import logging
import os
import re
import shutil
import sys
from typing import Dict, List, Optional

logger = logging.getLogger("rtms.hardware")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # rtms_app/
_FFMPEG_BIN = os.path.join(_BASE_DIR, "bin", "ffmpeg.exe")


def get_ffmpeg_bin() -> str:
    """
    Retorna la ruta al binario FFmpeg.
    Prioriza el binario empaquetado en bin/ffmpeg.exe,
    luego el binario en PATH del sistema,
    y finalmente la ruta por defecto _FFMPEG_BIN.
    """
    if os.path.exists(_FFMPEG_BIN):
        return _FFMPEG_BIN
    system_bin = shutil.which("ffmpeg")
    if system_bin:
        return system_bin
    return _FFMPEG_BIN


def has_ffmpeg_binary() -> bool:
    """Verifica si el binario FFmpeg está físicamente disponible en disco o en PATH."""
    return os.path.exists(_FFMPEG_BIN) or (shutil.which("ffmpeg") is not None)


async def get_directshow_devices() -> List[Dict[str, str]]:
    """
    Llama a ffmpeg -list_devices true -f dshow -i dummy de forma asíncrona y
    analiza stderr para extraer el Nombre Amigable (Friendly Name) y la Ruta del Dispositivo (Alternative name).
    Retorna una lista de diccionarios: [{"friendly_name": "...", "device_path": "..."}]
    """
    ffmpeg_bin = get_ffmpeg_bin()
    if not has_ffmpeg_binary():
        logger.error(f"No se encontró el binario FFmpeg en {_FFMPEG_BIN} ni en PATH del sistema")
        return []

    logger.info("Sondeando dispositivos DirectShow...")
    try:
        process = await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            "-list_devices",
            "true",
            "-f",
            "dshow",
            "-i",
            "dummy",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_WIN_FLAGS,
        )

        _, stderr = await process.communicate()
        output = stderr.decode("utf-8", errors="ignore")

        return parse_dshow_output(output)
    except Exception as e:
        logger.exception(f"Error consultando dispositivos DirectShow: {e}")
        return []


def parse_dshow_output(output: str) -> List[Dict[str, str]]:
    r"""
    Analiza la salida stderr de ffmpeg dshow.
    Soporta formatos antiguos y el formato moderno de FFmpeg 7.x/8.x.
    Filtra estrictamente dispositivos de audio DirectShow (KSCATEGORY_AUDIO / @device_cm_).
    """
    devices: List[Dict[str, str]] = []
    lines = output.split("\n")

    # Audio GUIDs y prefijos en DirectShow que NUNCA deben capturarse como video
    AUDIO_DEVICE_MARKERS = [
        "@device_cm_",
        "33d9a762-90c8-11d0-bd43-00a0c911ce86",  # CLSID_AudioInputDeviceCategory
        "4df0a701-02cd-11cf-8356-0080c73df13a",  # KSCATEGORY_AUDIO
    ]

    def is_audio_device(name: str, path: str) -> bool:
        path_lower = path.lower()
        if any(marker in path_lower for marker in AUDIO_DEVICE_MARKERS):
            return True
        name_lower = name.lower()
        if "(audio)" in name_lower:
            return True
        return False

    # 1. Detectar si la salida corresponde al formato moderno de FFmpeg 7.x+:
    # Formato: [in#0 @ 0000...] "Name" (video) / (audio) / (none)
    has_modern_format = any(
        ("]" in line and ("(video)" in line or "(audio)" in line or "(none)" in line)) or "[in#" in line
        for line in lines
    )

    if has_modern_format:
        current_video_device = None
        for line in lines:
            if "(video)" in line and "]" in line:
                m = re.search(r'"([^"]+)"\s*\(video\)', line)
                if m:
                    current_video_device = m.group(1)
            elif "Alternative name" in line and current_video_device:
                m = re.search(r'Alternative name\s+"([^"]+)"', line)
                if m:
                    dev_path = m.group(1)
                    if not is_audio_device(current_video_device, dev_path):
                        devices.append({"friendly_name": current_video_device, "device_path": dev_path})
                current_video_device = None
            elif "(audio)" in line or "(none)" in line:
                current_video_device = None

        logger.info(f"Se encontraron {len(devices)} dispositivos de video (formato moderno).")
        return devices

    # 2. Fallback al formato clásico de FFmpeg (6.x y anteriores)
    if "DirectShow audio devices" in output:
        video_part = output.split("DirectShow audio devices")[0]
    else:
        video_part = output

    current_device = None
    for line in video_part.split("\n"):
        if "DirectShow video devices" in line or "(audio)" in line or "(none)" in line:
            continue
        if "Alternative name" in line and current_device:
            m = re.search(r'Alternative name\s+"([^"]+)"', line)
            if m:
                dev_path = m.group(1)
                if not is_audio_device(current_device, dev_path):
                    devices.append({"friendly_name": current_device, "device_path": dev_path})
            current_device = None
        elif "]" in line and '"' in line:
            m = re.search(r'"([^"]+)"', line)
            if m:
                candidate = m.group(1)
                if "(audio)" not in line.lower():
                    current_device = candidate

    logger.info(f"Se encontraron {len(devices)} dispositivos de video (formato clásico).")
    return devices


class HardwareCapabilityDetector:
    """
    Detector y caché singleton global de capacidades de aceleración por hardware.
    Elimina la ejecución redundante de subprocesos de prueba de encoders mediante caché compartida.
    """

    _instance = None

    def __init__(self):
        self._capabilities: Dict[str, bool] = {}
        self._lock = asyncio.Lock()
        self._tested = False

    @classmethod
    def get_instance(cls) -> "HardwareCapabilityDetector":
        if cls._instance is None:
            cls._instance = HardwareCapabilityDetector()
        return cls._instance

    async def get_available_encoders(self) -> List[str]:
        async with self._lock:
            if not self._tested:
                await self._probe_capabilities()
            return [enc for enc, ok in self._capabilities.items() if ok]

    async def is_encoder_supported(self, encoder: str) -> bool:
        if encoder == "libx264":
            return True
        async with self._lock:
            if not self._tested:
                await self._probe_capabilities()
            return self._capabilities.get(encoder, False)

    async def get_best_encoder(self, preferred_order: Optional[List[str]] = None) -> str:
        if preferred_order is None:
            preferred_order = ["h264_nvenc", "h264_qsv", "h264_amf"]
        available = await self.get_available_encoders()
        for enc in preferred_order:
            if enc in available:
                return enc
        return "libx264"

    async def _probe_capabilities(self):
        if not has_ffmpeg_binary():
            logger.warning("FFmpeg no disponible. Aceleración por hardware desactivada.")
            self._capabilities = {"h264_nvenc": False, "h264_qsv": False, "h264_amf": False, "libx264": True}
            self._tested = True
            return

        logger.info("Detectando capacidades de codificación por hardware (Caché Global)...")
        ffmpeg_bin = get_ffmpeg_bin()
        encoders_to_test = ["h264_nvenc", "h264_qsv", "h264_amf"]

        for enc in encoders_to_test:
            try:
                p = await asyncio.create_subprocess_exec(
                    ffmpeg_bin,
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=640x360:d=0.1",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:v",
                    enc,
                    "-f",
                    "null",
                    "-",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    creationflags=_WIN_FLAGS,
                )
                await p.wait()
                is_supported = p.returncode == 0
                self._capabilities[enc] = is_supported
                if is_supported:
                    logger.info(f"Codificador por hardware validado y disponible en el sistema: {enc}")
            except Exception as e:
                logger.debug(f"Encoder {enc} no soportado: {e}")
                self._capabilities[enc] = False

        self._capabilities["libx264"] = True
        self._tested = True


hardware_detector = HardwareCapabilityDetector.get_instance()

_mjpeg_support_cache: Dict[str, bool] = {}


async def probe_device_mjpeg_support(raw_device: str) -> bool:
    """
    Sondea si un dispositivo DirectShow físico expone un pin de captura con compresión MJPEG.
    Retorna True si el dispositivo soporta pixel_format=mjpeg o vcodec=mjpeg.
    Retorna False para dispositivos virtuales o cámaras sin pin de compresión MJPEG (solo YUYV/NV12).
    Los resultados se almacenan en caché para evitar sondeos redundantes de subprocesos.
    """
    if not raw_device or raw_device.startswith("virtual://") or raw_device.startswith("testsrc"):
        return False
    if raw_device in _mjpeg_support_cache:
        return _mjpeg_support_cache[raw_device]

    ffmpeg_bin = get_ffmpeg_bin()
    if not has_ffmpeg_binary():
        _mjpeg_support_cache[raw_device] = False
        return False

    escaped_device = raw_device.replace(":", "\\:")
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-list_options",
        "true",
        "-f",
        "dshow",
        "-i",
        f"video={escaped_device}",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_WIN_FLAGS,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        output = stderr.decode("utf-8", errors="ignore").lower()
        supports_mjpeg = "pixel_format=mjpeg" in output or "vcodec=mjpeg" in output
        _mjpeg_support_cache[raw_device] = supports_mjpeg
        if supports_mjpeg:
            logger.info(f"[{raw_device}] Pin de compresión MJPEG validado en sensor DirectShow.")
        else:
            logger.info(f"[{raw_device}] Pin MJPEG no disponible en DirectShow (ingesta nativa YUYV/NV12 requerida).")
        return supports_mjpeg
    except Exception as e:
        logger.debug(f"Aviso al sondear soporte MJPEG en {raw_device}: {e}")
        _mjpeg_support_cache[raw_device] = False
        return False
