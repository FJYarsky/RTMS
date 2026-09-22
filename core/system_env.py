# ==============================================================================
# RTMS — Real-Time Multicam System
# Configuración y utilidades del entorno del sistema Windows.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Configuración y utilidades del entorno de ejecución del sistema operativo Windows.
Re-exporta funciones de energía desde core.power_mgr para máxima compatibilidad.
"""

import logging
import os
import subprocess
import sys
from typing import Any, Dict

from core.power_mgr import (
    BACKUP_FILE,
    BALANCED_GUID,
    ES_AWAYMODE_REQUIRED,
    ES_CONTINUOUS,
    ES_DISPLAY_REQUIRED,
    ES_SYSTEM_REQUIRED,
    HIGH_PERFORMANCE_GUID,
    POWER_SAVER_GUID,
    ULTIMATE_PERFORMANCE_GUID,
    DynamicPowerGovernor,
    acquire_stay_awake,
    apply_network_power_settings,
    backup_current_power_settings,
    get_active_scheme_guid,
    get_base_dir,
    get_hibernate_enabled,
    get_net_adapters_pnp,
    get_power_setting,
    is_admin,
    power_governor,
    release_stay_awake,
    restore_original_power_settings,
    set_active_scheme,
    setup_windows_environment,
)

__all__ = [
    "BACKUP_FILE",
    "BALANCED_GUID",
    "ES_AWAYMODE_REQUIRED",
    "ES_CONTINUOUS",
    "ES_DISPLAY_REQUIRED",
    "ES_SYSTEM_REQUIRED",
    "HIGH_PERFORMANCE_GUID",
    "POWER_SAVER_GUID",
    "ULTIMATE_PERFORMANCE_GUID",
    "DynamicPowerGovernor",
    "acquire_stay_awake",
    "apply_network_power_settings",
    "backup_current_power_settings",
    "get_active_scheme_guid",
    "get_base_dir",
    "get_hibernate_enabled",
    "get_net_adapters_pnp",
    "get_platform_details",
    "get_power_setting",
    "is_admin",
    "power_governor",
    "release_stay_awake",
    "remove_firewall_rules",
    "restore_original_power_settings",
    "set_active_scheme",
    "setup_firewall_rules",
    "setup_windows_environment",
    "unblock_app_binaries",
]

logger = logging.getLogger("rtms.system_env")

_WIN_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def unblock_app_binaries() -> int:
    """
    Elimina los flujos de datos alternativos NTFS de Mark-of-the-Web (:Zone.Identifier)
    de todos los archivos ejecutables, bibliotecas (.dll, .pyd) y configuraciones
    en el directorio de la aplicación en Windows.

    Previene bloqueos de seguridad de .NET Framework / CLR (como 'Failed to resolve Python.Runtime.Loader.Initialize')
    al descomprimir el release zip descargado de la web. Retorna el número de archivos desbloqueados.
    """
    if sys.platform != "win32":
        return 0

    cleaned = 0
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        base_dirs = []
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            base_dirs.append(exe_dir)
            base_dirs.append(os.path.join(exe_dir, "_internal"))
            if hasattr(sys, "_MEIPASS"):
                base_dirs.append(sys._MEIPASS)
        else:
            base_dirs.append(get_base_dir())

        target_exts = (".dll", ".exe", ".pyd", ".json", ".config", ".ico", ".py")
        for bdir in set(base_dirs):
            if not os.path.exists(bdir):
                continue
            for root, _, files in os.walk(bdir):
                for f in files:
                    if f.lower().endswith(target_exts):
                        fpath = os.path.join(root, f)
                        zone_path = fpath + ":Zone.Identifier"
                        if kernel32.DeleteFileW(zone_path):
                            cleaned += 1
    except Exception as e:
        logger.debug(f"Aviso al desbloquear binarios de la aplicación: {e}")

    if cleaned > 0:
        logger.info(f"Se desbloquearon {cleaned} archivos con marca de descarga web (Zone.Identifier).")
    return cleaned


def setup_firewall_rules(port_range: str = "8889-8990,9000-9200") -> bool:
    """Agrega o actualiza reglas en el firewall para puertos SRT/UDP y WebRTC sin duplicación."""
    if sys.platform != "win32":
        return False

    if not is_admin():
        logger.debug("Privilegios de administrador no detectados; omitiendo configuración automática de Firewall.")
        return False

    logger.info(f"Verificando y configurando regla de firewall RTMS_Media_Ports ({port_range})...")
    try:
        # Verificar si la regla ya existe
        check_cmd = ["netsh", "advfirewall", "firewall", "show", "rule", "name=RTMS_Media_Ports"]
        check_res = subprocess.run(
            check_cmd, check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW
        )
        if check_res.returncode == 0:
            logger.info("Regla RTMS_Media_Ports ya existente detectada; renovando...")
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", "name=RTMS_Media_Ports"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=_WIN_NO_WINDOW,
            )

        cmd_fw_srt = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            "name=RTMS_Media_Ports",
            "dir=in",
            "action=allow",
            "protocol=UDP",
            f"localport={port_range}",
            "profile=private",
        ]
        res = subprocess.run(
            cmd_fw_srt, check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW
        )
        if res.returncode == 0:
            logger.info("Reglas del Firewall de Windows configuradas exitosamente.")
            return True
        err_msg = (res.stderr or res.stdout or "").strip()
        logger.warning(f"netsh retornó código {res.returncode}: {err_msg}")
        return False
    except Exception as e:
        logger.error(f"Error al configurar firewall: {e}")
        return False


def remove_firewall_rules() -> bool:
    """Elimina la regla de firewall creada por RTMS."""
    if sys.platform != "win32":
        return False
    try:
        cmd = ["netsh", "advfirewall", "firewall", "delete", "rule", "name=RTMS_Media_Ports"]
        res = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW)
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Error al remover regla de firewall: {e}")
        return False


def get_platform_details() -> Dict[str, Any]:
    """
    Identifica de forma exhaustiva la versión de Windows, edición comercial,
    número de compilación, UBR y arquitectura de hardware.
    """
    import platform

    machine = platform.machine()
    arch = (
        "64-bit (x64)" if machine in ("AMD64", "x86_64") else ("ARM64" if "arm" in machine.lower() else "32-bit (x86)")
    )
    info = {
        "os": "Windows" if sys.platform == "win32" else sys.platform.capitalize(),
        "edition": "Windows",
        "version": platform.version(),
        "display_version": "",
        "build": "",
        "build_number": "",
        "ubr": "",
        "arch": arch,
        "architecture": arch,
        "machine": machine,
        "summary": "Windows",
    }

    if sys.platform != "win32":
        info["summary"] = f"{platform.system()} {platform.release()} ({arch})"
        return info

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            info["edition"] = winreg.QueryValueEx(k, "ProductName")[0]
            try:
                info["display_version"] = winreg.QueryValueEx(k, "DisplayVersion")[0]
            except FileNotFoundError:
                pass
            try:
                info["build"] = str(winreg.QueryValueEx(k, "CurrentBuildNumber")[0])
                info["build_number"] = info["build"]
            except FileNotFoundError:
                pass
            try:
                info["ubr"] = str(winreg.QueryValueEx(k, "UBR")[0])
            except FileNotFoundError:
                pass
    except Exception as e:
        logger.debug(f"Aviso consultando registro de versión de Windows: {e}")

    ver_tag = f" ({info['display_version']})" if info["display_version"] else ""
    build_tag = (
        f" — Compilación {info['build']}.{info['ubr']}"
        if (info["build"] and info["ubr"])
        else (f" — Compilación {info['build']}" if info["build"] else "")
    )
    info["summary"] = f"{info['edition']}{ver_tag}{build_tag} [{info['arch']}]"
    return info
