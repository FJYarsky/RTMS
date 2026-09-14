# ==============================================================================
# RTMS — Real-Time Multicam System
# Desarrollado y soporte: Junio 2026 - Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import asyncio
import re
import os
import sys
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("rtms.hardware")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # rtms_app/
_FFMPEG_BIN = os.path.join(_BASE_DIR, "bin", "ffmpeg.exe")

async def get_directshow_devices() -> List[Dict[str, str]]:
    """
    Llama a ffmpeg -list_devices true -f dshow -i dummy de forma asíncrona y
    analiza stderr para extraer el Nombre Amigable (Friendly Name) y la Ruta del Dispositivo (Alternative name).
    Retorna una lista de diccionarios: [{"friendly_name": "...", "device_path": "..."}]
    """
    if not os.path.exists(_FFMPEG_BIN):
        logger.error(f"No se encontró el binario FFmpeg en {_FFMPEG_BIN}")
        return []

    logger.info("Sondeando dispositivos DirectShow...")
    try:
        process = await asyncio.create_subprocess_exec(
            _FFMPEG_BIN, "-list_devices", "true", "-f", "dshow", "-i", "dummy",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_WIN_FLAGS
        )
        
        _, stderr = await process.communicate()
        output = stderr.decode('utf-8', errors='ignore')
        
        return parse_dshow_output(output)
    except Exception as e:
        logger.exception(f"Error consultando dispositivos DirectShow: {e}")
        return []

def parse_dshow_output(output: str) -> List[Dict[str, str]]:
    r"""
    Analiza la salida stderr de ffmpeg dshow.
    Soporta formatos antiguos y el nuevo formato de FFmpeg 7.x.
    """
    devices = []
    lines = output.split('\n')
    
    # 1. Intentar el formato moderno de FFmpeg 7.x:
    # [in#0 @ 0000...] "Name" (video)
    # [in#0 @ 0000...]   Alternative name "@device..."
    current_video_device = None
    has_modern_format = False
    
    for line in lines:
        if '(video)' in line and ']' in line:
            has_modern_format = True
            m = re.search(r'"([^"]+)"\s*\(video\)', line)
            if m:
                current_video_device = m.group(1)
        elif 'Alternative name' in line and current_video_device:
            m = re.search(r'Alternative name\s+"([^"]+)"', line)
            if m:
                devices.append({
                    "friendly_name": current_video_device,
                    "device_path": m.group(1)
                })
            current_video_device = None
        elif '(audio)' in line or '(none)' in line:
            current_video_device = None
            
    if has_modern_format:
        logger.info(f"Se encontraron {len(devices)} dispositivos de video.")
        return devices
        
    # 2. Fallback al formato clásico de FFmpeg (6.x y anteriores)
    if "DirectShow audio devices" in output:
        video_part = output.split("DirectShow audio devices")[0]
    else:
        video_part = output
        
    current_device = None
    for line in video_part.split('\n'):
        if "DirectShow video devices" in line:
            continue
        if "Alternative name" in line and current_device:
            m = re.search(r'Alternative name\s+"([^"]+)"', line)
            if m:
                devices.append({
                    "friendly_name": current_device,
                    "device_path": m.group(1)
                })
            current_device = None
        elif "]" in line and '"' in line:
            m = re.search(r'"([^"]+)"', line)
            if m:
                current_device = m.group(1)
                
    logger.info(f"Se encontraron {len(devices)} dispositivos de video.")
    return devices
