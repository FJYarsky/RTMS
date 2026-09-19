# ==============================================================================
# RTMS — Real-Time Multicam System
# Gestión profesional de energía y rendimiento de Windows.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Gestión nativa de perfiles de energía, prevención de suspensión y optimización
del entorno Windows para streaming en vivo de alta estabilidad y baja latencia.
Utiliza exclusivamente Win32 APIs (powrprof.dll, kernel32) y manipulación directa
de registro (winreg) sin scripts externos de PowerShell.
"""

import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("rtms.power_mgr")

_WIN_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# GUIDs estándar de esquemas de energía de Windows
HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
POWER_SAVER_GUID = "a1841308-3541-4fab-bc81-f71556f20b4a"
ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"

# Subgrupos y parámetros de configuración powercfg
SUB_SLEEP_GUID = "238c27d7-2e2d-47d2-a56e-df0e11f6c163"
STANDBY_IDLE_GUID = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"
SUB_USB_GUID = "2a737441-1930-4402-8d77-b2bebba308a3"
USB_SUSPEND_GUID = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"

# Flags de SetThreadExecutionState
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040


def get_base_dir() -> str:
    """Retorna el directorio base de la aplicación."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BACKUP_FILE = os.path.join(get_base_dir(), "config", "power_backup.json")


def is_admin() -> bool:
    """Verifica si el proceso actual cuenta con privilegios elevados de Administrador en Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_active_scheme_guid() -> Optional[str]:
    """
    Obtiene el GUID del plan de energía activo de Windows.
    Intenta primero la API nativa de powrprof.dll y recurre a powercfg en caso necesario.
    """
    if sys.platform != "win32":
        return None

    # Método 1: Powrprof.dll PowerGetActiveScheme
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        p_guid = ctypes.POINTER(GUID)()
        powrprof = ctypes.windll.powrprof
        if powrprof.PowerGetActiveScheme(None, ctypes.byref(p_guid)) == 0 and p_guid:
            guid_struct = p_guid.contents
            d4_str = (
                "".join(f"{b:02x}" for b in guid_struct.Data4[:2])
                + "-"
                + "".join(f"{b:02x}" for b in guid_struct.Data4[2:])
            )
            guid_str = f"{guid_struct.Data1:08x}-{guid_struct.Data2:04x}-{guid_struct.Data3:04x}-{d4_str}".lower()
            ctypes.windll.kernel32.LocalFree(p_guid)
            return guid_str
    except Exception as e:
        logger.debug(f"Aviso leyendo esquema vía powrprof: {e}")

    # Método 2: Fallback vía powercfg
    try:
        import re

        res = subprocess.run(
            ["powercfg", "-getactivescheme"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            creationflags=_WIN_NO_WINDOW,
        )
        match = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            res.stdout,
        )
        if match:
            return match.group(0).lower()
    except Exception as e:
        logger.warning(f"Error al obtener GUID del plan activo: {e}")
    return None


def set_active_scheme(guid_str: str) -> bool:
    """
    Establece el plan de energía activo por su GUID.
    Intenta powrprof.dll PowerSetActiveScheme y recurre a powercfg si es necesario.
    """
    if sys.platform != "win32" or not guid_str:
        return False

    clean_guid = guid_str.strip().lower()

    # Método 1: powrprof PowerSetActiveScheme
    try:
        import ctypes
        import uuid

        py_uuid = uuid.UUID(clean_guid)
        bytes_le = py_uuid.bytes_le

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_uint8 * 8),
            ]

        data1 = int.from_bytes(bytes_le[0:4], "little")
        data2 = int.from_bytes(bytes_le[4:6], "little")
        data3 = int.from_bytes(bytes_le[6:8], "little")
        data4 = (ctypes.c_uint8 * 8)(*bytes_le[8:16])
        g = GUID(data1, data2, data3, data4)

        if ctypes.windll.powrprof.PowerSetActiveScheme(None, ctypes.byref(g)) == 0:
            logger.info(f"Plan de energía {clean_guid} activado vía powrprof.")
            return True
    except Exception as e:
        logger.debug(f"Aviso activando plan vía powrprof: {e}")

    # Método 2: Fallback powercfg
    try:
        res = subprocess.run(
            ["powercfg", "-setactive", clean_guid],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            creationflags=_WIN_NO_WINDOW,
        )
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Error activando plan de energía {clean_guid}: {e}")
        return False


def acquire_stay_awake() -> bool:
    """Evita la suspensión automática del sistema y pantalla mientras RTMS esté operando activamente."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        res = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
        if res != 0:
            logger.info("Modo activo de ejecución habilitado (SetThreadExecutionState).")
            return True
        return False
    except Exception as e:
        logger.warning(f"No se pudo configurar SetThreadExecutionState: {e}")
        return False


def release_stay_awake() -> bool:
    """Restaura el comportamiento normal de suspensión del sistema."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        logger.info("Modo de suspensión normal restaurado.")
        return True
    except Exception as e:
        logger.debug(f"No se pudo restaurar SetThreadExecutionState: {e}")
        return False


def get_net_adapters_pnp() -> Dict[str, Optional[int]]:
    """Obtiene los valores actuales de PnPCapabilities para todos los adaptadores de red registrados."""
    if sys.platform != "win32":
        return {}
    import winreg

    adapters = {}
    path = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = path + "\\" + subkey_name
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                        try:
                            winreg.QueryValueEx(subkey, "NetCfgInstanceId")
                            pnp_val = None
                            try:
                                pnp_val, _ = winreg.QueryValueEx(subkey, "PnPCapabilities")
                            except FileNotFoundError:
                                pass
                            adapters[subkey_name] = pnp_val
                        except FileNotFoundError:
                            pass
                    i += 1
                except OSError:
                    break
    except Exception as e:
        logger.warning(f"Error consultando adaptadores de red en el registro: {e}")
    return adapters


def apply_network_power_settings() -> bool:
    """
    Desactiva el ahorro de energía en todos los adaptadores de red físicos/lógicos
    modificando PnPCapabilities a 24 directamente a través de winreg.
    CERO uso de PowerShell para evitar falsos positivos de antivirus.
    Requiere permisos de administrador; si no los tiene, retorna False limpiamente.
    """
    if sys.platform != "win32":
        return False

    if not is_admin():
        logger.info("Privilegios de administrador no disponibles para configurar adaptadores de red.")
        return False

    import winreg

    path = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}"
    updated_any = False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = path + "\\" + subkey_name
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
                        ) as subkey:
                            try:
                                winreg.QueryValueEx(subkey, "NetCfgInstanceId")
                                # PnPCapabilities = 24 (0x18) desactiva ahorro de energía en el adaptador
                                winreg.SetValueEx(subkey, "PnPCapabilities", 0, winreg.REG_DWORD, 24)
                                updated_any = True
                            except FileNotFoundError:
                                pass
                    except PermissionError:
                        pass
                    i += 1
                except OSError:
                    break
    except Exception as e:
        logger.warning(f"Error modificando PnPCapabilities en registro: {e}")
        return False

    return updated_any


def get_hibernate_enabled() -> int:
    """Obtiene el estado actual de hibernación desde el registro de Windows."""
    if sys.platform != "win32":
        return 1
    import winreg

    path = r"SYSTEM\CurrentControlSet\Control\Power"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            val, _ = winreg.QueryValueEx(key, "HibernateEnabled")
            return val
    except Exception as e:
        logger.debug(f"No se pudo consultar HibernateEnabled en el registro: {e}")
        return 1


def get_power_setting(subgroup: str, setting: str) -> Tuple[Optional[int], Optional[int]]:
    """Consulta los índices de AC y DC para un subgrupo y ajuste de energía."""
    if sys.platform != "win32":
        return None, None
    try:
        import re

        res = subprocess.run(
            ["powercfg", "/q", "SCHEME_CURRENT", subgroup, setting],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=_WIN_NO_WINDOW,
        )
    except Exception as e:
        logger.warning(f"Error ejecutando powercfg: {e}")
        return None, None

    ac_val = None
    dc_val = None
    for line in res.stdout.splitlines():
        line_l = line.lower()
        is_ac = (
            "current ac" in line_l
            or "ac power" in line_l
            or "alterna" in line_l
            or ("ac" in line_l and "index" in line_l)
        )
        is_dc = (
            "current dc" in line_l
            or "dc power" in line_l
            or "continua" in line_l
            or "bater" in line_l
            or ("dc" in line_l and "index" in line_l)
        )
        m = re.search(r"0x[0-9a-fA-F]+", line)
        if not m:
            continue
        val = int(m.group(0), 16)
        if is_ac and ac_val is None:
            ac_val = val
        elif is_dc and dc_val is None:
            dc_val = val

    return ac_val, dc_val


def backup_current_power_settings():
    """Crea un respaldo atómico de las directivas originales de energía y adaptadores de red."""
    if sys.platform != "win32":
        return

    if os.path.exists(BACKUP_FILE):
        logger.info("El archivo de respaldo de energía ya existe. Omitiendo para preservar originales.")
        return

    logger.info("Creando respaldo de configuraciones originales de energía...")
    try:
        active_guid = get_active_scheme_guid()
        standby_ac, standby_dc = get_power_setting("SUB_SLEEP", "STANDBYIDLE")
        usb_ac, usb_dc = get_power_setting(SUB_USB_GUID, USB_SUSPEND_GUID)
        disk_ac, disk_dc = get_power_setting("SUB_DISK", "DISKIDLE")
        monitor_ac, monitor_dc = get_power_setting("SUB_VIDEO", "MONITORIDLE")

        hibernate = get_hibernate_enabled()
        adapters = get_net_adapters_pnp()

        backup_data = {
            "active_scheme_guid": active_guid,
            "hibernate_enabled": hibernate,
            "adapters": adapters,
            "timeouts": {
                "standby-timeout-ac": standby_ac,
                "standby-timeout-dc": standby_dc,
                "usb-timeout-ac": usb_ac,
                "usb-timeout-dc": usb_dc,
                "disk-timeout-ac": disk_ac,
                "disk-timeout-dc": disk_dc,
                "monitor-timeout-ac": monitor_ac,
                "monitor-timeout-dc": monitor_dc,
            },
        }

        os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
        tmp_backup = BACKUP_FILE + ".tmp"
        with open(tmp_backup, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_backup, BACKUP_FILE)

        logger.info(f"Respaldo de energía guardado atómicamente en {BACKUP_FILE}")
    except Exception as e:
        logger.error(f"Error al realizar respaldo de energía: {e}")


def restore_original_power_settings() -> Dict[str, Any]:
    """Restaura la configuración de energía y red a su estado original previo a las optimizaciones."""
    if sys.platform != "win32":
        return {"status": "error", "message": "No en Windows"}

    if not os.path.exists(BACKUP_FILE):
        return {"status": "error", "message": "No se encontró respaldo original de energía"}

    logger.info("Restaurando configuraciones originales de energía...")
    try:
        import winreg

        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            backup = json.load(f)

        active_guid = backup.get("active_scheme_guid")
        if active_guid:
            set_active_scheme(active_guid)

        timeouts = backup.get("timeouts", {})

        def restore_val(subgroup, setting, ac_key, dc_key):
            if not active_guid:
                return
            ac_val = timeouts.get(ac_key)
            dc_val = timeouts.get(dc_key)
            if ac_val is not None:
                subprocess.run(
                    ["powercfg", "-setacvalueindex", active_guid, subgroup, setting, str(ac_val)],
                    check=False,
                    creationflags=_WIN_NO_WINDOW,
                )
            if dc_val is not None:
                subprocess.run(
                    ["powercfg", "-setdcvalueindex", active_guid, subgroup, setting, str(dc_val)],
                    check=False,
                    creationflags=_WIN_NO_WINDOW,
                )

        restore_val("SUB_SLEEP", "STANDBYIDLE", "standby-timeout-ac", "standby-timeout-dc")
        restore_val(SUB_USB_GUID, USB_SUSPEND_GUID, "usb-timeout-ac", "usb-timeout-dc")
        restore_val("SUB_DISK", "DISKIDLE", "disk-timeout-ac", "disk-timeout-dc")
        restore_val("SUB_VIDEO", "MONITORIDLE", "monitor-timeout-ac", "monitor-timeout-dc")

        if active_guid:
            set_active_scheme(active_guid)

        # Restaurar HibernateEnabled
        hibernate_val = backup.get("hibernate_enabled", 1)
        path = r"SYSTEM\CurrentControlSet\Control\Power"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "HibernateEnabled", 0, winreg.REG_DWORD, hibernate_val)
        except Exception as e:
            logger.debug(f"Aviso al restaurar HibernateEnabled: {e}")

        # Restaurar adaptadores de red
        adapters = backup.get("adapters", {})
        class_path = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}"
        for subkey_name, original_val in adapters.items():
            subkey_path = class_path + "\\" + subkey_name
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_SET_VALUE) as subkey:
                    if original_val is None:
                        try:
                            winreg.DeleteValue(subkey, "PnPCapabilities")
                        except FileNotFoundError:
                            pass
                    else:
                        winreg.SetValueEx(subkey, "PnPCapabilities", 0, winreg.REG_DWORD, original_val)
            except Exception as e:
                logger.debug(f"Aviso al restaurar adaptador {subkey_name}: {e}")

        try:
            os.remove(BACKUP_FILE)
        except OSError as e:
            logger.debug(f"Aviso al remover archivo backup: {e}")

        logger.info("Configuración original restaurada completamente.")
        return {"status": "ok", "message": "Restauración completada con éxito"}
    except Exception as e:
        logger.error(f"Error durante la restauración energética: {e}")
        return {"status": "error", "message": "Fallo interno durante la restauración energética"}


def setup_windows_environment() -> Dict[str, Any]:
    """
    Configura el entorno de Windows para streaming ininterrumpido sin utilizar
    scripts de PowerShell. Reporta el estado transparente de cada modificación.
    """
    if sys.platform != "win32":
        return {
            "status": "error",
            "message": "Plataforma no soportada (solo Windows)",
            "applied": [],
            "failed": ["No se encuentra en Windows"],
            "warnings": [],
        }

    applied: List[str] = []
    failed: List[str] = []
    warnings: List[str] = []

    backup_current_power_settings()
    logger.info("Aplicando optimizaciones de estabilidad y energía en Windows (modo nativo)...")

    # 1. Suspender USB Selective Suspend en plan activo
    active_guid = get_active_scheme_guid()
    if active_guid:
        try:
            r1 = subprocess.run(
                ["powercfg", "-setacvalueindex", active_guid, SUB_USB_GUID, USB_SUSPEND_GUID, "0"],
                check=False,
                capture_output=True,
                timeout=15,
                creationflags=_WIN_NO_WINDOW,
            )
            r2 = subprocess.run(
                ["powercfg", "-setdcvalueindex", active_guid, SUB_USB_GUID, USB_SUSPEND_GUID, "0"],
                check=False,
                capture_output=True,
                timeout=15,
                creationflags=_WIN_NO_WINDOW,
            )
            set_active_scheme(active_guid)
            if r1.returncode == 0 and r2.returncode == 0:
                applied.append("Suspensión selectiva USB desactivada (AC y DC)")
            else:
                failed.append("Fallo al configurar suspensión selectiva USB")
        except Exception as e:
            logger.error(f"Error en configuración USB: {e}")
            failed.append("Fallo al configurar suspensión selectiva USB")
    else:
        warnings.append(
            "No se pudo detectar el GUID del plan de energía activo; omitiendo cambios dependientes de GUID"
        )

    # 2. Desactivar suspensión de equipo y apagado de disco/pantalla
    cmds_to_run = [
        (["powercfg", "/change", "standby-timeout-ac", "0"], "Suspensión del sistema en AC deshabilitada"),
        (["powercfg", "/change", "standby-timeout-dc", "0"], "Suspensión del sistema en DC deshabilitada"),
        (["powercfg", "/hibernate", "off"], "Hibernación deshabilitada"),
        (["powercfg", "/change", "disk-timeout-ac", "0"], "Apagado de disco en AC deshabilitado"),
        (["powercfg", "/change", "disk-timeout-dc", "0"], "Apagado de disco en DC deshabilitado"),
        (["powercfg", "/change", "monitor-timeout-ac", "0"], "Apagado de monitor en AC deshabilitado"),
        (["powercfg", "/change", "monitor-timeout-dc", "0"], "Apagado de monitor en DC deshabilitado"),
    ]

    for cmd, desc in cmds_to_run:
        try:
            res = subprocess.run(cmd, check=False, capture_output=True, timeout=15, creationflags=_WIN_NO_WINDOW)
            if res.returncode == 0:
                applied.append(desc)
            else:
                failed.append(f"Fallo en: {desc} (code {res.returncode})")
        except Exception as exc:
            logger.error(f"Excepción en {desc}: {exc}")
            failed.append(f"Fallo al ejecutar: {desc}")

    # 3. Optimización de red (sin PowerShell)
    if is_admin():
        if apply_network_power_settings():
            applied.append("Ahorro de energía en adaptadores de red desactivado (vía winreg)")
        else:
            warnings.append("No se encontraron adaptadores de red para actualizar en el registro")
    else:
        warnings.append("Ahorro de energía de red omitido (requiere permisos de Administrador)")

    status_str = "ok"
    if failed and applied:
        status_str = "partial"
    elif failed and not applied:
        status_str = "failed"

    return {
        "status": status_str,
        "message": f"Optimizaciones finalizadas con estado: {status_str}",
        "applied": applied,
        "failed": failed,
        "warnings": warnings,
    }


class DynamicPowerGovernor:
    """
    Gobernador dinámico de energía para RTMS.
    Activa automáticamente el plan de Alto Rendimiento cuando hay transmisiones activas
    y restaura el plan de energía anterior cuando todas las transmisiones han finalizado.
    """

    def __init__(self):
        self._original_scheme: Optional[str] = None
        self._is_boosted: bool = False
        self._lock_held: bool = False

    def on_stream_started(self, active_streams_count: int) -> None:
        """Notificación de inicio de transmisión."""
        if sys.platform != "win32":
            return

        acquire_stay_awake()
        self._lock_held = True

        if active_streams_count >= 1 and not self._is_boosted:
            current = get_active_scheme_guid()
            if current and current.lower() != HIGH_PERFORMANCE_GUID.lower():
                self._original_scheme = current
                if set_active_scheme(HIGH_PERFORMANCE_GUID):
                    self._is_boosted = True
                    logger.info("Plan de Alto Rendimiento activado dinámicamente durante streaming.")

    def on_stream_stopped(self, active_streams_count: int) -> None:
        """Notificación de detención de transmisión."""
        if sys.platform != "win32":
            return

        if active_streams_count == 0:
            if self._is_boosted and self._original_scheme:
                set_active_scheme(self._original_scheme)
                logger.info(f"Plan de energía original ({self._original_scheme}) restaurado.")
                self._is_boosted = False
                self._original_scheme = None

            release_stay_awake()
            self._lock_held = False

    def shutdown(self) -> None:
        """Restaura cualquier esquema modificado y libera directivas."""
        if self._is_boosted and self._original_scheme:
            set_active_scheme(self._original_scheme)
            self._is_boosted = False
            self._original_scheme = None
        if self._lock_held:
            release_stay_awake()
            self._lock_held = False


power_governor = DynamicPowerGovernor()
