# ==============================================================================
# RTMS v2.2.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import json
import os
import sys
import re
import uuid
import secrets
import logging
import threading
from typing import Dict, Any, Optional

from core.__version__ import __version__
from core.secrets_mgr import protect_secret, unprotect_secret
from core.port_mgr import port_manager

logger = logging.getLogger("rtms.config_mgr")

_CONFIG_LOCK = threading.Lock()
_LAST_SAVED_CONFIG: Optional[str] = None

def get_base_dir() -> str:
    """Retorna el directorio base persistente, evitando carpetas temporales de PyInstaller."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = os.path.join(get_base_dir(), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CONFIG_BAK_FILE = os.path.join(CONFIG_DIR, "config.json.bak")
CONFIG_TMP_FILE = os.path.join(CONFIG_DIR, "config.json.tmp")

CURRENT_SCHEMA_VERSION = 3

VIRTUAL_DEVICE_KEYWORDS = [
    "virtual", "obs virtual", "elgato virtual", "vmix", "unity",
    "manycam", "droidcam", "splitcam", "snap camera", "ndi", "iriun",
    "nvidia broadcast", "broadcast"
]

# Perfiles de cámara predefinidos (Presets)
CAMERA_PRESETS: Dict[str, Dict[str, Any]] = {
    "low_latency_720p": {
        "name": "Baja Latencia (720p @ 30fps)",
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2500,
        "srt_latency": 100,
        "zerolatency": True,
        "protocol": "srt"
    },
    "broadcast_1080p": {
        "name": "Broadcast HD (1080p @ 60fps)",
        "resolution": "1080p",
        "fps": 60,
        "bitrate": 6000,
        "srt_latency": 200,
        "zerolatency": False,
        "protocol": "srt"
    },
    "high_quality_4k": {
        "name": "Alta Calidad 4K (4K @ 30fps)",
        "resolution": "4K",
        "fps": 30,
        "bitrate": 18000,
        "srt_latency": 300,
        "zerolatency": False,
        "protocol": "srt"
    },
    "cpu_compatible": {
        "name": "Compatibilidad Universal CPU (720p @ 30fps)",
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2000,
        "encoder": "libx264",
        "srt_latency": 150,
        "zerolatency": True,
        "protocol": "srt"
    }
}

def is_virtual_device(friendly_name: str) -> bool:
    name_lower = friendly_name.lower()
    return any(kw in name_lower for kw in VIRTUAL_DEVICE_KEYWORDS)

def generate_stable_camera_id(device_path: str, friendly_name: str = "") -> str:
    """Genera un UUID v5 estable y determinista para la cámara basado en su identificador físico DirectShow."""
    seed = device_path.lower()
    # Priorizar VID/PID de PNP locator para que el ID sea resistente a cambios de puerto USB
    m = re.search(r'(vid_[0-9a-f]+&pid_[0-9a-f]+(?:&mi_[0-9a-f]+)?)', seed)
    if m:
        seed = m.group(1)
    elif "{" in seed and "}" in seed:
        m_guid = re.search(r'\{[0-9a-f\-]+\}', seed)
        if m_guid:
            seed = m_guid.group(0)
    return f"cam_{uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:12]}"

def migrate_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migra configuraciones heredadas hacia el esquema más reciente de forma incremental.
    v1 -> v2 (2.0.2 / 2.0.3) -> v3 (v2.0.4 / v2.1.0 / v2.2.0 con camera_id y passphrases seguras).
    """
    schema_ver = data.get("config_schema_version", 1)

    if schema_ver < 2:
        logger.info("Migrando configuración v1 -> v2...")
        data["unattended_autostart"] = data.get("unattended_autostart", True)
        data["next_port"] = data.get("next_port", 9000)
        for dp, cam in data.get("cameras", {}).items():
            cam.setdefault("protocol", "srt")
            cam.setdefault("zerolatency", True)
            cam.setdefault("srt_latency", 120)
            if not cam.get("srt_passphrase"):
                cam["srt_passphrase"] = secrets.token_hex(6)
        schema_ver = 2

    if schema_ver < 3:
        logger.info("Migrando configuración v2 -> v3 (Identidad estable y protección de credenciales)...")
        for dp, cam in data.get("cameras", {}).items():
            if "id" not in cam:
                cam["id"] = generate_stable_camera_id(dp)
            # Asegurar que el puerto quede registrado
            port = cam.get("port")
            if port:
                try:
                    port_manager.register_port(int(port))
                except Exception:
                    pass
        data["config_schema_version"] = 3

    data["version"] = __version__
    return data

def load_config() -> Dict[str, Any]:
    """
    Carga la configuración desde disco de forma protegida contra concurrencia y corrupción.
    Si el archivo está dañado, intenta recuperar desde .bak automáticamente.
    """
    with _CONFIG_LOCK:
        if not os.path.exists(CONFIG_DIR):
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
            except Exception as e:
                logger.error(f"No se pudo crear el directorio de configuración {CONFIG_DIR}: {e}")

        default_config = {
            "version": __version__,
            "config_schema_version": CURRENT_SCHEMA_VERSION,
            "cameras": {},
            "next_port": 9000,
            "unattended_autostart": True
        }

        if not os.path.exists(CONFIG_FILE):
            # Si no existe config.json pero existe backup, restaurar desde backup
            if os.path.exists(CONFIG_BAK_FILE):
                try:
                    with open(CONFIG_BAK_FILE, "r", encoding="utf-8") as fb:
                        data = json.load(fb)
                        logger.warning("Restaurando configuración principal desde backup (.bak)...")
                        _atomic_save_unlocked(data)
                        return _unprotect_config_cameras(migrate_config(data))
                except Exception as e:
                    logger.error(f"Error restaurando desde backup: {e}")

            _atomic_save_unlocked(default_config)
            return default_config

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                migrated = migrate_config(data)
                # Registrar puertos ya configurados en el PortManager
                for cam in migrated.get("cameras", {}).values():
                    p = cam.get("port")
                    if p:
                        try:
                            port_manager.register_port(int(p))
                        except (ValueError, TypeError) as pe:
                            logger.warning(f"Puerto corrupto ignorado en configuración: {p!r} ({pe})")
                return _unprotect_config_cameras(migrated)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Configuración corrupta o ilegible ({e}). Intentando recuperación desde backup...")
            if os.path.exists(CONFIG_BAK_FILE):
                try:
                    with open(CONFIG_BAK_FILE, "r", encoding="utf-8") as fb:
                        data = json.load(fb)
                        migrated = migrate_config(data)
                        _atomic_save_unlocked(migrated)
                        return _unprotect_config_cameras(migrated)
                except Exception as eb:
                    logger.error(f"Fallo también la lectura del backup: {eb}")

            # Fallback seguro
            _atomic_save_unlocked(default_config)
            return default_config

def _unprotect_config_cameras(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Descifra las passphrases de las cámaras en memoria para que el sistema las use en claro."""
    cameras = config_data.get("cameras", {})
    for cam in cameras.values():
        raw_pass = cam.get("srt_passphrase", "")
        if raw_pass:
            cam["srt_passphrase"] = unprotect_secret(raw_pass)
    return config_data

def _prepare_config_for_disk(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Copia la configuración y protege las credenciales antes de persistir en disco."""
    disk_copy = json.loads(json.dumps(config_data))
    disk_copy["version"] = __version__
    disk_copy["config_schema_version"] = CURRENT_SCHEMA_VERSION
    for cam in disk_copy.get("cameras", {}).values():
        raw_pass = cam.get("srt_passphrase", "")
        if raw_pass:
            cam["srt_passphrase"] = protect_secret(raw_pass)
    return disk_copy

def _atomic_save_unlocked(config_data: Dict[str, Any]):
    """
    Guarda en disco con escritura atómica (.tmp -> fsync -> .bak -> replace).
    Sin lock interno. Deduplica en memoria contra la configuración lógica en claro
    para no generar I/O ni fsync innecesarios por la aleatoriedad de DPAPI (Claude #6).
    """
    global _LAST_SAVED_CONFIG
    current_serialized = json.dumps(config_data, sort_keys=True)
    if _LAST_SAVED_CONFIG is not None and _LAST_SAVED_CONFIG == current_serialized and os.path.exists(CONFIG_FILE):
        return

    disk_data = _prepare_config_for_disk(config_data)
    json_bytes = json.dumps(disk_data, indent=4, ensure_ascii=False).encode("utf-8")

    os.makedirs(CONFIG_DIR, exist_ok=True)

    # 1. Escribir a archivo temporal
    with open(CONFIG_TMP_FILE, "wb") as tf:
        tf.write(json_bytes)
        tf.flush()
        os.fsync(tf.fileno())

    # 2. Mantener copia de backup antes de reemplazar
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "rb") as src, open(CONFIG_BAK_FILE, "wb") as dst:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
        except OSError as be:
            logger.debug(f"Aviso al actualizar .bak: {be}")

    # 3. Reemplazo atómico
    os.replace(CONFIG_TMP_FILE, CONFIG_FILE)
    _LAST_SAVED_CONFIG = current_serialized

def save_config(config_data: Dict[str, Any]):
    """Persiste la configuración de forma atómica y protegida por cerrojo."""
    with _CONFIG_LOCK:
        try:
            _atomic_save_unlocked(config_data)
        except Exception as e:
            logger.error(f"Error al guardar atómicamente la configuración: {e}")

def get_or_allocate_camera_config(device_path: str, friendly_name: str) -> Dict[str, Any]:
    """Retorna la configuración de una cámara, asignando ID estable, puerto libre verificado y passphrase segura."""
    config = load_config()
    cameras = config.get("cameras", {})
    virtual_flag = is_virtual_device(friendly_name)
    cam_id = generate_stable_camera_id(device_path)

    if device_path in cameras:
        cam = cameras[device_path]
        cam["friendly_name"] = friendly_name
        cam.setdefault("id", cam_id)
        cam.setdefault("auto_start", not virtual_flag)
        cam.setdefault("zerolatency", True)
        cam.setdefault("is_virtual", virtual_flag)
        cam.setdefault("protocol", "srt")
        if not cam.get("srt_passphrase"):
            cam["srt_passphrase"] = secrets.token_hex(6)

        # Verificar que el puerto esté registrado
        port = cam.get("port")
        if port:
            port_manager.register_port(int(port))

        save_config(config)
        return cam

    # Asignar nuevo puerto validado por PortManager
    preferred = config.get("next_port", 9000)
    try:
        port = port_manager.allocate_port(preferred)
        config["next_port"] = port + 1
    except Exception as exc:
        logger.warning(f"Error asignando puerto mediante PortManager: {exc}. Usando fallback.")
        port = preferred
        config["next_port"] = preferred + 1

    default_passphrase = secrets.token_hex(6)

    new_cam_config = {
        "id": cam_id,
        "friendly_name": friendly_name,
        "device_path": device_path,
        "port": port,
        "resolution": "720p",
        "fps": 30,
        "bitrate": 3000,
        "protocol": "srt",
        "encoder": "auto",
        "srt_latency": 120,
        "srt_passphrase": default_passphrase,
        "zerolatency": True,
        "auto_start": not virtual_flag,
        "is_virtual": virtual_flag
    }

    cameras[device_path] = new_cam_config
    config["cameras"] = cameras
    save_config(config)

    return new_cam_config

def find_camera_by_id_or_path(identifier: str) -> Optional[Dict[str, Any]]:
    """Busca una cámara por su camera_id (UUID) o por su device_path."""
    config = load_config()
    cameras = config.get("cameras", {})
    if identifier in cameras:
        return cameras[identifier]
    for cam in cameras.values():
        if cam.get("id") == identifier:
            return cam
    return None

def update_camera_config(device_path: str, resolution: str, fps: int, bitrate: int,
                          protocol: str = "srt", encoder: str = "auto",
                          srt_latency: int = 120, srt_passphrase: str = "",
                          auto_start: bool = True, zerolatency: bool = True,
                          is_virtual: bool = False):
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cam = cameras[device_path]
        cam["resolution"] = resolution
        cam["fps"] = fps
        cam["bitrate"] = bitrate
        cam["protocol"] = protocol
        cam["encoder"] = encoder
        cam["srt_latency"] = srt_latency
        if srt_passphrase:
            cam["srt_passphrase"] = srt_passphrase
        cam["auto_start"] = auto_start
        cam["zerolatency"] = zerolatency
        cam["is_virtual"] = is_virtual
        save_config(config)

def set_camera_autostart(device_path: str, auto_start: bool):
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cameras[device_path]["auto_start"] = auto_start
        save_config(config)

def apply_camera_preset(device_path: str, preset_key: str) -> Optional[Dict[str, Any]]:
    """Aplica un perfil predeterminado a una cámara existente."""
    if preset_key not in CAMERA_PRESETS:
        return None
    preset = CAMERA_PRESETS[preset_key]
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cam = cameras[device_path]
        for k, v in preset.items():
            if k != "name":
                cam[k] = v
        save_config(config)
        return cam
    return None

def export_config(safe_mode: bool = True, include_secrets: bool = False) -> Dict[str, Any]:
    """
    Exporta la configuración completa lista para backup o transporte entre equipos.
    En modo seguro (por defecto), enmascara las contraseñas SRT para proteger
    secretos (P0-02 / Claude #2).
    """
    cfg = load_config()
    export_data = json.loads(json.dumps(cfg))

    if safe_mode and not include_secrets:
        for cam in export_data.get("cameras", {}).values():
            if cam.get("srt_passphrase"):
                cam["srt_passphrase"] = "••••••••"
                cam["has_passphrase"] = True
        export_data["secrets_redacted"] = True
    else:
        export_data["secrets_redacted"] = False

    return export_data

def import_config(new_config: Dict[str, Any]) -> bool:
    """Importa y valida una configuración externa, aplicando migraciones necesarias."""
    if not isinstance(new_config, dict):
        return False
    cameras = new_config.get("cameras")
    if not isinstance(cameras, dict):
        return False
    for cam in cameras.values():
        if not isinstance(cam, dict):
            return False
    try:
        migrated = migrate_config(new_config)
        save_config(migrated)
        return True
    except Exception as e:
        logger.error(f"Fallo durante la importación y migración de configuración: {e}")
        return False
