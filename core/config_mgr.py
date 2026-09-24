# ==============================================================================
# RTMS — Real-Time Multicam System
# Gestión y persistencia de la configuración del sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Gestión, validación, migración y persistencia atómica de la configuración del sistema."""

import json
import logging
import os
import re
import sys
import threading
import uuid
from typing import Any, Dict, Optional

from core.__version__ import __version__
from core.port_mgr import port_manager
from core.secrets_mgr import protect_secret, unprotect_secret

logger = logging.getLogger("rtms.config_mgr")

_CONFIG_LOCK = threading.Lock()
_LAST_SAVED_CONFIG: Optional[str] = None


def get_base_dir() -> str:
    r"""
    Retorna el directorio base persistente, evitando carpetas temporales de PyInstaller.
    Verifica que el directorio sea escribible; si no lo es (ej. C:\Program Files\),
    cae a %LOCALAPPDATA%\RTMS\.
    """
    base = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    test_file = os.path.join(base, ".rtms_perm_check")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(test_file)
        return base
    except Exception:
        local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        fallback = os.path.join(local_app, "RTMS")
        try:
            os.makedirs(fallback, exist_ok=True)
        except Exception:
            pass
        return fallback


CONFIG_DIR = os.path.join(get_base_dir(), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CONFIG_BAK_FILE = os.path.join(CONFIG_DIR, "config.json.bak")
CONFIG_LEGACY_BAK_FILE = os.path.join(CONFIG_DIR, "config.json.legacy_v2_bak")
CONFIG_TMP_FILE = os.path.join(CONFIG_DIR, "config.json.tmp")

CURRENT_SCHEMA_VERSION = 4

VIRTUAL_DEVICE_KEYWORDS = [
    "virtual",
    "obs virtual",
    "elgato virtual",
    "vmix",
    "unity",
    "manycam",
    "droidcam",
    "splitcam",
    "snap camera",
    "ndi",
    "iriun",
    "nvidia broadcast",
    "broadcast",
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
        "protocol": "srt",
    },
    "broadcast_1080p": {
        "name": "Broadcast HD (1080p @ 60fps)",
        "resolution": "1080p",
        "fps": 60,
        "bitrate": 6000,
        "srt_latency": 200,
        "zerolatency": False,
        "protocol": "srt",
    },
    "high_quality_4k": {
        "name": "Alta Calidad 4K (4K @ 30fps)",
        "resolution": "4K",
        "fps": 30,
        "bitrate": 18000,
        "srt_latency": 300,
        "zerolatency": False,
        "protocol": "srt",
    },
    "cpu_compatible": {
        "name": "Compatibilidad Universal CPU (720p @ 30fps)",
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2000,
        "encoder": "libx264",
        "srt_latency": 150,
        "zerolatency": True,
        "protocol": "srt",
    },
}


def is_virtual_device(friendly_name: str) -> bool:
    name_lower = friendly_name.lower()
    return any(kw in name_lower for kw in VIRTUAL_DEVICE_KEYWORDS)


class UnsupportedConfigSchemaError(ValueError):
    """Excepción levantada cuando un archivo de configuración posee una versión de esquema posterior no soportada."""

    pass


class LegacyConfigSchemaError(ValueError):
    """Excepción levantada cuando un archivo de configuración posee una versión de esquema previa no soportada (< 4)."""

    pass


class ConfigPersistenceError(RuntimeError):
    """Excepción levantada cuando ocurre un error al persistir la configuración en disco."""

    pass


def generate_stable_camera_id(device_path: str, friendly_name: str = "") -> str:
    """
    Genera un identificador UUID v5 estable y determinista para la cámara.
    Utiliza la ruta física DirectShow normalizada completa para asegurar que dos dispositivos
    del mismo modelo (mismo VID/PID) en diferentes puertos USB obtengan IDs únicos y estables en el sistema.
    """
    seed = device_path.lower().strip()
    if not seed and friendly_name:
        seed = friendly_name.lower().strip()
    match = re.search(r"vid_([0-9a-fA-F]{4})&pid_([0-9a-fA-F]{4})", seed)
    if match:
        vid, pid = match.groups()
        return f"cam_{vid.lower()}_{pid.lower()}_{uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:8]}"
    return f"cam_{uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:12]}"


def migrate_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida la configuración contra el esquema v4 oficial de RTMS v2.4.0.
    Rechaza esquemas heredados incompatibles (< 4) con LegacyConfigSchemaError
    y esquemas futuros desconocidos (> 4) con UnsupportedConfigSchemaError.
    """
    schema_ver = data.get("config_schema_version", 1)

    if schema_ver > CURRENT_SCHEMA_VERSION:
        raise UnsupportedConfigSchemaError(
            f"Versión de esquema {schema_ver} no soportada por RTMS v{__version__} (máxima soportada: {CURRENT_SCHEMA_VERSION})."
        )

    if schema_ver < CURRENT_SCHEMA_VERSION:
        raise LegacyConfigSchemaError(
            f"Versión de esquema heredada ({schema_ver} < {CURRENT_SCHEMA_VERSION}) no compatible con RTMS v2.4.0+. "
            "La retrocompatibilidad para versiones previas ha sido descontinuada para garantizar la estabilidad."
        )

    for dp, cam in data.get("cameras", {}).items():
        if isinstance(cam, dict):
            if "id" not in cam:
                cam["id"] = generate_stable_camera_id(dp, cam.get("friendly_name", ""))
            port = cam.get("port")
            if port:
                try:
                    port_manager.register_port(int(port))
                except Exception:
                    pass

    data.setdefault("ignored_devices", [])
    data.setdefault("mediamtx_srt_port", 8890)
    data["version"] = __version__
    return data


def load_config() -> Dict[str, Any]:
    """
    Carga la configuración desde disco de forma protegida contra concurrencia y corrupción.
    Si detecta una versión heredada previa a v2.4.0 (< 4), crea un respaldo en
    'config.json.legacy_v2_bak' y reinicializa la configuración limpia para v2.4.0.
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
            "ignored_devices": [],
            "next_port": 9000,
            "unattended_autostart": False,
            "mediamtx_srt_port": 8890,
        }

        # Inicialización / Migración automática desde JSON hacia SQLite WAL
        try:
            from core.repository.migrator import auto_migrate_json_to_sqlite

            auto_migrate_json_to_sqlite(CONFIG_FILE)
        except Exception as me:
            logger.debug(f"Migración inicial a SQLite WAL omitida o no requerida: {me}")

        if not os.path.exists(CONFIG_FILE):
            # 1. Intentar recuperación prioritaria desde base de datos SQLite WAL (rtms.db)
            try:
                from core.repository.config_repository import config_repository
                from core.repository.migrator import export_sqlite_to_json

                if config_repository.get_all_cameras_sync() or config_repository.get_system_settings_sync():
                    logger.warning("Restaurando configuración principal desde base de datos SQLite WAL (rtms.db)...")
                    if export_sqlite_to_json(CONFIG_FILE):
                        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            return _unprotect_config_cameras(migrate_config(data))
            except Exception as dbe:
                logger.debug(f"Recuperación previa desde SQLite WAL omitida o fallida: {dbe}")

            # 2. Si no existe en SQLite, intentar restaurar desde backup (.bak)
            if os.path.exists(CONFIG_BAK_FILE):
                try:
                    with open(CONFIG_BAK_FILE, "r", encoding="utf-8") as fb:
                        data = json.load(fb)
                        logger.warning("Restaurando configuración principal desde backup (.bak)...")
                        _atomic_save_unlocked(data)
                        return _unprotect_config_cameras(migrate_config(data))
                except LegacyConfigSchemaError as lce:
                    logger.warning(f"Backup heredado (< 4) detectado: {lce}. Reinicializando configuración limpia.")
                except Exception as e:
                    logger.error(f"Error restaurando desde backup: {e}")

            # 3. Fallback inicial con configuración por defecto
            _atomic_save_unlocked(default_config)
            return default_config

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                f"Configuración corrupta o ilegible ({e}). Intentando recuperación desde SQLite WAL o backup..."
            )
            # 1. Intentar recuperación desde SQLite WAL
            try:
                from core.repository.config_repository import config_repository
                from core.repository.migrator import export_sqlite_to_json

                if config_repository.get_all_cameras_sync() or config_repository.get_system_settings_sync():
                    logger.warning("Restaurando configuración corrupta desde SQLite WAL (rtms.db)...")
                    if export_sqlite_to_json(CONFIG_FILE):
                        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            return _unprotect_config_cameras(migrate_config(data))
            except Exception as dbe:
                logger.debug(f"Recuperación desde SQLite WAL fallida: {dbe}")

            # 2. Intentar recuperación desde backup (.bak)
            if os.path.exists(CONFIG_BAK_FILE):
                try:
                    with open(CONFIG_BAK_FILE, "r", encoding="utf-8") as fb:
                        data = json.load(fb)
                        logger.warning("Restaurando configuración principal desde backup (.bak)...")
                        _atomic_save_unlocked(data)
                        return _unprotect_config_cameras(migrate_config(data))
                except LegacyConfigSchemaError as lce_bak:
                    logger.warning(f"Backup heredado (< 4) detectado: {lce_bak}. Reinicializando configuración limpia.")
                except Exception as ex_bak:
                    logger.error(f"Error restaurando desde backup: {ex_bak}")

            # 3. Fallback inicial con configuración por defecto
            _atomic_save_unlocked(default_config)
            return default_config

        try:
            migrated = migrate_config(data)
        except LegacyConfigSchemaError as lce:
            logger.warning(
                f"Configuración heredada detectada: {lce}. "
                f"Creando respaldo en {CONFIG_LEGACY_BAK_FILE} y reinicializando configuración limpia para v2.4.0."
            )
            try:
                import shutil

                shutil.copy2(CONFIG_FILE, CONFIG_LEGACY_BAK_FILE)
            except Exception as be:
                logger.error(f"Error creando respaldo de configuración heredada: {be}")
            _atomic_save_unlocked(default_config)
            return default_config

        # Registrar puertos ya configurados en el PortManager
        for cam in migrated.get("cameras", {}).values():
            p = cam.get("port")
            if p:
                try:
                    port_manager.register_port(int(p))
                except (ValueError, TypeError) as pe:
                    logger.warning(f"Puerto corrupto ignorado en configuración: {p!r} ({pe})")
        return _unprotect_config_cameras(migrated)


def _unprotect_config_cameras(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Descifra las passphrases de las cámaras en memoria para que el sistema las use en claro."""
    cameras = config_data.get("cameras", {})
    for cam in cameras.values():
        raw_pass = cam.get("srt_passphrase", "")
        if raw_pass:
            try:
                cam["srt_passphrase"] = unprotect_secret(raw_pass, raise_on_error=True)
                cam["decryption_failed"] = False
            except Exception as e:
                logger.warning(
                    f"Error descifrando credencial de cámara {cam.get('friendly_name', '')}: {e}. Marcando como irrecuperable."
                )
                cam["srt_passphrase"] = ""
                cam["decryption_failed"] = True
                cam["credential_unavailable"] = True
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
        # Purgar campos efímeros de runtime para no persistir URLs derivadas ni flags temporales
        cam.pop("_url", None)
        cam.pop("_actual_encoder", None)
        cam.pop("decryption_failed", None)
    return disk_copy


def _atomic_save_unlocked(config_data: Dict[str, Any]):
    """
    Guarda en disco con persistencia coordinada entre SQLite WAL (ACID) y JSON atómico.
    Sin lock interno. Deduplica en memoria contra la configuración lógica en claro
    para no generar operaciones de I/O ni fsync innecesarios cuando no hay cambios de contenido.
    """
    global _LAST_SAVED_CONFIG
    current_serialized = json.dumps(config_data, sort_keys=True)
    if _LAST_SAVED_CONFIG is not None and _LAST_SAVED_CONFIG == current_serialized and os.path.exists(CONFIG_FILE):
        return

    disk_data = _prepare_config_for_disk(config_data)
    json_bytes = json.dumps(disk_data, indent=4, ensure_ascii=False).encode("utf-8")

    os.makedirs(CONFIG_DIR, exist_ok=True)

    # 1. Guardar primero en base de datos SQLite WAL transaccional (ACID)
    try:
        from core.repository.config_repository import config_repository

        config_repository.save_full_config_sync(disk_data)
    except Exception as dbe:
        logger.error(f"Fallo en transacción SQLite WAL al persistir configuración: {dbe}")
        raise ConfigPersistenceError(f"Fallo en base de datos SQLite: {dbe}") from dbe

    # 2. Escribir a archivo temporal con fsync
    try:
        with open(CONFIG_TMP_FILE, "wb") as tf:
            tf.write(json_bytes)
            tf.flush()
            os.fsync(tf.fileno())

        # 3. Mantener copia de backup antes de reemplazar
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "rb") as src, open(CONFIG_BAK_FILE, "wb") as dst:
                    dst.write(src.read())
                    dst.flush()
                    os.fsync(dst.fileno())
            except OSError as be:
                logger.debug(f"Aviso al actualizar .bak: {be}")

        # 4. Reemplazo atómico
        os.replace(CONFIG_TMP_FILE, CONFIG_FILE)
        _LAST_SAVED_CONFIG = current_serialized
    except Exception as io_err:
        if os.path.exists(CONFIG_TMP_FILE):
            try:
                os.remove(CONFIG_TMP_FILE)
            except Exception:
                pass
        logger.error(f"Fallo escribiendo archivo JSON de configuración: {io_err}")
        raise ConfigPersistenceError(f"Fallo en I/O de archivo JSON: {io_err}") from io_err


def save_config(config_data: Dict[str, Any], raise_on_error: bool = False) -> bool:
    """Persiste la configuración de forma atómica y protegida por cerrojo. Retorna True si tuvo éxito."""
    with _CONFIG_LOCK:
        try:
            _atomic_save_unlocked(config_data)
            return True
        except Exception as e:
            logger.error(f"Error al guardar atómicamente la configuración: {e}")
            if raise_on_error:
                raise ConfigPersistenceError(f"Fallo de persistencia en disco: {e}") from e
            return False


def get_or_allocate_camera_config(device_path: str, friendly_name: str) -> Dict[str, Any]:
    """Retorna la configuración de una cámara, asignando ID estable, puerto libre verificado y passphrase segura."""
    config = load_config()
    cameras = config.get("cameras", {})
    virtual_flag = is_virtual_device(friendly_name)
    cam_id = generate_stable_camera_id(device_path, friendly_name)

    if device_path in cameras:
        cam = cameras[device_path]
        cam["friendly_name"] = friendly_name
        cam.setdefault("id", cam_id)
        cam.setdefault("auto_start", False)
        cam.setdefault("zerolatency", True)
        cam.setdefault("is_virtual", virtual_flag)
        cam.setdefault("protocol", "srt")
        cam.setdefault("udp_mode", "multicast")
        cam.setdefault("udp_host", "127.0.0.1")
        if not cam.get("srt_passphrase") and not cam.get("decryption_failed"):
            cam["srt_passphrase"] = ""

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
        logger.error(f"Error asignando puerto mediante PortManager: {exc}. No se puede asignar a ciegas.")
        raise RuntimeError(f"Agotamiento de puertos multimedia: {exc}") from exc

    default_passphrase = ""

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
        "auto_start": False,
        "is_virtual": virtual_flag,
        "udp_mode": "multicast",
        "udp_host": "127.0.0.1",
    }

    cameras[device_path] = new_cam_config
    config["cameras"] = cameras
    save_config(config)

    return new_cam_config


def find_camera_by_id_or_path(identifier: str) -> Optional[Dict[str, Any]]:
    """Busca una cámara por su camera_id (UUID), clave de diccionario o device_path."""
    config = load_config()
    cameras = config.get("cameras", {})
    if identifier in cameras:
        return cameras[identifier]
    for cam in cameras.values():
        if cam.get("id") == identifier or cam.get("device_path") == identifier:
            return cam
    return None


def update_camera_config(
    device_path: str,
    resolution: str,
    fps: int,
    bitrate: int,
    protocol: str = "srt",
    encoder: str = "auto",
    srt_latency: int = 120,
    srt_passphrase: Optional[str] = None,
    auto_start: Optional[bool] = None,
    zerolatency: bool = True,
    is_virtual: bool = False,
    udp_mode: str = "multicast",
    udp_host: str = "127.0.0.1",
):
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
        if srt_passphrase is not None:
            cam["srt_passphrase"] = srt_passphrase
        if auto_start is not None:
            cam["auto_start"] = auto_start
        cam["zerolatency"] = zerolatency
        cam["is_virtual"] = is_virtual
        cam["udp_mode"] = udp_mode
        cam["udp_host"] = udp_host
        return save_config(config)
    return False


def set_camera_autostart(device_path: str, auto_start: bool) -> bool:
    config = load_config()
    cameras = config.get("cameras", {})
    if device_path in cameras:
        cameras[device_path]["auto_start"] = auto_start
        return save_config(config)
    return False


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
        if save_config(config):
            return cam
        return None
    return None


def export_config(safe_mode: bool = True, include_secrets: bool = False) -> Dict[str, Any]:
    """
    Exporta la configuración completa lista para backup o transporte entre equipos.
    En modo seguro (por defecto), enmascara las contraseñas SRT para proteger
    secretos y credenciales de acceso.
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
    """Importa y valida una configuración externa, aplicando migraciones de esquema necesarias."""
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
        return save_config(migrated)
    except Exception as e:
        logger.error(f"Fallo durante la importación y migración de configuración: {e}")
        return False


def remove_camera_config(identifier: str) -> bool:
    """
    Elimina permanentemente la configuración de una cámara por su device_path o ID,
    liberando su puerto y agregándola a ignored_devices para prevenir auto-detección.
    """
    config = load_config()
    cameras = config.get("cameras", {})
    target_key = None
    if identifier in cameras:
        target_key = identifier
    else:
        for key, cam in cameras.items():
            if cam.get("id") == identifier or cam.get("device_path") == identifier:
                target_key = key
                break

    if target_key:
        removed_cam = cameras.pop(target_key)
        dp = removed_cam.get("device_path", target_key)
        friendly_name = removed_cam.get("friendly_name") or removed_cam.get("name") or dp
        ignored = config.setdefault("ignored_devices", [])
        already_ignored = any(
            (item == dp if isinstance(item, str) else item.get("device_path") == dp) for item in ignored
        )
        if not already_ignored:
            from datetime import datetime, timezone

            ignored.append(
                {
                    "device_path": dp,
                    "friendly_name": friendly_name,
                    "ignored_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        port = removed_cam.get("port")
        if port:
            try:
                port_manager.release_port(int(port))
            except Exception:
                pass
        return save_config(config)
    return False


def get_ignored_devices() -> list[dict]:
    """Retorna la lista de dispositivos ignorados en formato uniforme de diccionarios."""
    config = load_config()
    res = []
    for item in config.get("ignored_devices", []):
        if isinstance(item, str):
            res.append({"device_path": item, "friendly_name": item, "ignored_at": None})
        elif isinstance(item, dict):
            res.append(
                {
                    "device_path": item.get("device_path", ""),
                    "friendly_name": item.get("friendly_name") or item.get("device_path", ""),
                    "ignored_at": item.get("ignored_at"),
                }
            )
    return res


def unignore_device(device_path: str) -> bool:
    """Permite readmitir un dispositivo DirectShow previamente descartado o ignorado."""
    config = load_config()
    ignored = config.get("ignored_devices", [])
    found = False
    new_ignored = []
    for item in ignored:
        dp = item if isinstance(item, str) else item.get("device_path")
        if dp == device_path:
            found = True
        else:
            new_ignored.append(item)
    if found:
        config["ignored_devices"] = new_ignored
        return save_config(config)
    return False


def clear_ignored_devices() -> bool:
    """Limpia completamente la lista de dispositivos ignorados."""
    config = load_config()
    config["ignored_devices"] = []
    return save_config(config)


def is_device_ignored(device_path: str) -> bool:
    """Verifica si un dispositivo se encuentra en la lista de ignorados."""
    config = load_config()
    for item in config.get("ignored_devices", []):
        if isinstance(item, str) and item == device_path:
            return True
        if isinstance(item, dict) and item.get("device_path") == device_path:
            return True
    return False
