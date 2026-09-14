# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.3
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import json
import os
import sys
import secrets
import logging
from typing import Dict, Any

logger = logging.getLogger("rtms.config_mgr")

def get_base_dir() -> str:
    """Retorna el directorio base persistente, evitando carpetas temporales de PyInstaller."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = os.path.join(get_base_dir(), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

VIRTUAL_DEVICE_KEYWORDS = [
    "virtual", "obs virtual", "elgato virtual", "vmix", "unity",
    "manycam", "droidcam", "splitcam", "snap camera", "ndi", "iriun"
]

def is_virtual_device(friendly_name: str) -> bool:
    name_lower = friendly_name.lower()
    return any(kw in name_lower for kw in VIRTUAL_DEVICE_KEYWORDS)

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"No se pudo crear el directorio de configuración {CONFIG_DIR}: {e}")

    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "version": "2.0.3",
            "cameras": {},
            "next_port": 9000,
            "unattended_autostart": True
        }
        save_config(default_config)
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["version"] = "2.0.3"
            return data
    except Exception as e:
        logger.error(f"Error al cargar la configuración: {e}")
        return {"version": "2.0.3", "cameras": {}, "next_port": 9000, "unattended_autostart": True}

def save_config(config_data: Dict[str, Any]):
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        logger.error(f"Error al guardar la configuración: {e}")

def get_or_allocate_camera_config(device_path: str, friendly_name: str) -> Dict[str, Any]:
    """Retorna la configuración de una cámara, asignando nuevo puerto y passphrase segura por defecto."""
    config = load_config()
    cameras = config.get("cameras", {})
    
    virtual_flag = is_virtual_device(friendly_name)

    if device_path in cameras:
        cameras[device_path]["friendly_name"] = friendly_name
        if "auto_start" not in cameras[device_path]:
            cameras[device_path]["auto_start"] = not virtual_flag
        if "zerolatency" not in cameras[device_path]:
            cameras[device_path]["zerolatency"] = True
        if "is_virtual" not in cameras[device_path]:
            cameras[device_path]["is_virtual"] = virtual_flag
        if "protocol" not in cameras[device_path]:
            cameras[device_path]["protocol"] = "srt"
        # Si no tenía passphrase, generar una segura
        if not cameras[device_path].get("srt_passphrase"):
            cameras[device_path]["srt_passphrase"] = secrets.token_hex(6)
        save_config(config)
        return cameras[device_path]

    # Asignar nuevo puerto
    port = config.get("next_port", 9000)
    config["next_port"] = port + 1

    # Seguridad: Passphrase segura de 12 caracteres generada aleatoriamente por defecto
    default_passphrase = secrets.token_hex(6)

    new_cam_config = {
        "friendly_name": friendly_name,
        "device_path": device_path,
        "port": port,
        "resolution": "720p",
        "fps": 30,
        "bitrate": 3000,
        "protocol": "srt",              # SRT por defecto
        "encoder": "auto",              # Auto-detectar GPU con fallback a libx264
        "srt_latency": 120,             # 120ms
        "srt_passphrase": default_passphrase,  # Contraseña segura por omisión
        "zerolatency": True,            # Parámetro zerolatency activado
        "auto_start": not virtual_flag, # Iniciar automáticamente salvo que sea virtual
        "is_virtual": virtual_flag
    }

    cameras[device_path] = new_cam_config
    config["cameras"] = cameras
    save_config(config)

    return new_cam_config

def update_camera_config(device_path: str, resolution: str, fps: int, bitrate: int,
                          protocol: str = "srt", encoder: str = "auto",
                          srt_latency: int = 120, srt_passphrase: str = "",
                          auto_start: bool = True, zerolatency: bool = True,
                          is_virtual: bool = False):
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cameras[device_path]["resolution"] = resolution
        cameras[device_path]["fps"] = fps
        cameras[device_path]["bitrate"] = bitrate
        cameras[device_path]["protocol"] = protocol
        cameras[device_path]["encoder"] = encoder
        cameras[device_path]["srt_latency"] = srt_latency
        cameras[device_path]["srt_passphrase"] = srt_passphrase
        cameras[device_path]["auto_start"] = auto_start
        cameras[device_path]["zerolatency"] = zerolatency
        cameras[device_path]["is_virtual"] = is_virtual
        save_config(config)

def set_camera_autostart(device_path: str, auto_start: bool):
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cameras[device_path]["auto_start"] = auto_start
        save_config(config)
