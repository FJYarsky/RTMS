# ==============================================================================
# RTMS v2.2.2 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import subprocess
import logging
import sys
import os
import re
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger("rtms.system_env")

_WIN_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKUP_FILE = os.path.join(get_base_dir(), "config", "power_backup.json")

def get_net_adapters_pnp():
    """Obtiene los valores actuales de PnPCapabilities para todos los adaptadores de red."""
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

def get_hibernate_enabled():
    """Obtiene el estado actual de hibernación desde el registro."""
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

def get_power_setting(subgroup: str, setting: str):
    """Consulta los índices actuales de AC y DC para una configuración de energía de forma silenciosa."""
    if sys.platform != "win32":
        return None, None
    try:
        res = subprocess.run(
            ["powercfg", "/q", "SCHEME_CURRENT", subgroup, setting],
            capture_output=True, text=True, check=False, timeout=10,
            creationflags=_WIN_NO_WINDOW
        )
    except Exception as e:
        logger.warning(f"Error ejecutando powercfg: {e}")
        return None, None

    ac_val = None
    dc_val = None
    lines = res.stdout.splitlines()

    for line in lines:
        line_l = line.lower()
        is_ac = ("current ac" in line_l or "ac power" in line_l
                 or "alterna" in line_l or ("ac" in line_l and "index" in line_l))
        is_dc = ("current dc" in line_l or "dc power" in line_l
                 or "continua" in line_l or "bater" in line_l
                 or ("dc" in line_l and "index" in line_l))

        m = re.search(r'0x[0-9a-fA-F]+', line)
        if not m:
            continue
        val = int(m.group(0), 16)
        if is_ac and ac_val is None:
            ac_val = val
        elif is_dc and dc_val is None:
            dc_val = val

    return ac_val, dc_val

def get_active_scheme_guid() -> Optional[str]:
    """Obtiene el GUID del plan de energía activo actual sin ventanas de consola."""
    if sys.platform != "win32":
        return None
    try:
        res = subprocess.run(
            ["powercfg", "-getactivescheme"],
            capture_output=True, text=True, check=False, timeout=5,
            creationflags=_WIN_NO_WINDOW
        )
        match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', res.stdout)
        if match:
            return match.group(0)
    except Exception as e:
        logger.warning(f"Error al obtener GUID del plan activo: {e}")
    return None

def backup_current_power_settings():
    """Realiza un respaldo de la configuración actual de energía y red."""
    if sys.platform != "win32":
        return

    if os.path.exists(BACKUP_FILE):
        logger.info("El archivo de respaldo de energía ya existe. Omitiendo respaldo para preservar los originales.")
        return

    logger.info("Creando respaldo de configuraciones originales de energía...")
    try:
        active_guid = get_active_scheme_guid()
        standby_ac, standby_dc = get_power_setting("SUB_SLEEP", "STANDBYIDLE")
        usb_ac, usb_dc = get_power_setting("2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226")
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
                "monitor-timeout-dc": monitor_dc
            }
        }

        os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)

        logger.info(f"Respaldo de energía guardado exitosamente en {BACKUP_FILE}")
    except Exception as e:
        logger.error(f"Error al realizar respaldo de energía: {e}")

def apply_network_power_settings() -> bool:
    """Desactiva el ahorro de energía en todos los adaptadores de red y Wake-on-LAN sin mostrar ventanas."""
    if sys.platform != "win32":
        return False

    ps_cmd_1 = (
        'Get-NetAdapter -ErrorAction SilentlyContinue | ForEach-Object { '
        '$instanceId = $_.DeviceID; '
        '$regPath = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4D36E972-E325-11CE-BFC1-08002BE10318}"; '
        'Get-ChildItem $regPath -ErrorAction SilentlyContinue | ForEach-Object { '
        '$path = $_.PSPath; '
        '$val = Get-ItemProperty -Path $path -Name "NetCfgInstanceId" -ErrorAction SilentlyContinue; '
        'if ($val -and $val.NetCfgInstanceId -eq $instanceId) { '
        'Set-ItemProperty -Path $path -Name "PnPCapabilities" -Value 24 -Type DWord -ErrorAction SilentlyContinue '
        '} } }'
    )

    ps_cmd_2 = (
        'Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {$_.Status -eq "Up"} | ForEach-Object { '
        '$_ | Set-NetAdapterPowerManagement -WakeOnMagicPacket Disabled -WakeOnPattern Disabled -ErrorAction SilentlyContinue '
        '}'
    )

    success = True
    try:
        r1 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_1], capture_output=True, text=True, check=False, timeout=15, creationflags=_WIN_NO_WINDOW)
        if r1.returncode != 0:
            success = False
        r2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_2], capture_output=True, text=True, check=False, timeout=15, creationflags=_WIN_NO_WINDOW)
        if r2.returncode != 0:
            success = False
    except Exception as e:
        logger.warning(f"No se pudo desactivar el ahorro de energía de los adaptadores de red: {e}")
        return False
    return success

def restore_original_power_settings() -> Dict[str, Any]:
    """Restaura la configuración de energía y red a su estado original previo a la optimización."""
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
            subprocess.run(["powercfg", "-setactive", active_guid], check=False, creationflags=_WIN_NO_WINDOW)

        timeouts = backup.get("timeouts", {})

        def restore_val(subgroup, setting, ac_key, dc_key):
            if not active_guid:
                return
            ac_val = timeouts.get(ac_key)
            dc_val = timeouts.get(dc_key)
            if ac_val is not None:
                subprocess.run(["powercfg", "-setacvalueindex", active_guid, subgroup, setting, str(ac_val)], check=False, creationflags=_WIN_NO_WINDOW)
            if dc_val is not None:
                subprocess.run(["powercfg", "-setdcvalueindex", active_guid, subgroup, setting, str(dc_val)], check=False, creationflags=_WIN_NO_WINDOW)

        restore_val("SUB_SLEEP", "STANDBYIDLE", "standby-timeout-ac", "standby-timeout-dc")
        restore_val("2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "usb-timeout-ac", "usb-timeout-dc")
        restore_val("SUB_DISK", "DISKIDLE", "disk-timeout-ac", "disk-timeout-dc")
        restore_val("SUB_VIDEO", "MONITORIDLE", "monitor-timeout-ac", "monitor-timeout-dc")

        if active_guid:
            subprocess.run(["powercfg", "-setactive", active_guid], check=False, creationflags=_WIN_NO_WINDOW)

        hibernate_val = backup.get("hibernate_enabled", 1)
        path = r"SYSTEM\CurrentControlSet\Control\Power"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "HibernateEnabled", 0, winreg.REG_DWORD, hibernate_val)
        except Exception as e:
            logger.debug(f"Aviso al restaurar HibernateEnabled: {e}")

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
        return {"status": "error", "message": f"Error: {e}"}

def setup_windows_environment() -> Dict[str, Any]:
    """
    Configura el entorno de Windows para streaming ininterrumpido y reporta
    el resultado de cada modificación de forma transparente.
    """
    if sys.platform != "win32":
        return {
            "status": "error",
            "message": "Plataforma no soportada (solo Windows)",
            "applied": [],
            "failed": ["No se encuentra en Windows"],
            "warnings": []
        }

    applied: List[str] = []
    failed: List[str] = []
    warnings: List[str] = []

    backup_current_power_settings()

    logger.info("Aplicando optimizaciones de estabilidad y energía en Windows...")

    # 1. Suspender USB Selective Suspend
    active_guid = get_active_scheme_guid()
    if active_guid:
        try:
            r1 = subprocess.run(["powercfg", "-setacvalueindex", active_guid, "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0"], check=False, capture_output=True, timeout=15, creationflags=_WIN_NO_WINDOW)
            r2 = subprocess.run(["powercfg", "-setdcvalueindex", active_guid, "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0"], check=False, capture_output=True, timeout=15, creationflags=_WIN_NO_WINDOW)
            subprocess.run(["powercfg", "-setactive", active_guid], check=False, capture_output=True, timeout=15, creationflags=_WIN_NO_WINDOW)
            if r1.returncode == 0 and r2.returncode == 0:
                applied.append("Suspensión selectiva USB desactivada (AC y DC)")
            else:
                failed.append("Fallo al configurar suspensión selectiva USB")
        except Exception as e:
            failed.append(f"Error en configuración USB: {e}")
    else:
        warnings.append("No se pudo detectar el GUID del plan de energía activo; omitiendo cambios dependientes de GUID")

    # 2. Desactivar suspensión de equipo y apagado de disco/pantalla
    cmds_to_run = [
        (["powercfg", "/change", "standby-timeout-ac", "0"], "Suspensión del sistema en AC deshabilitada"),
        (["powercfg", "/change", "standby-timeout-dc", "0"], "Suspensión del sistema en DC deshabilitada"),
        (["powercfg", "/hibernate", "off"], "Hibernación deshabilitada"),
        (["powercfg", "/change", "disk-timeout-ac", "0"], "Apagado de disco en AC deshabilitado"),
        (["powercfg", "/change", "disk-timeout-dc", "0"], "Apagado de disco en DC deshabilitado"),
        (["powercfg", "/change", "monitor-timeout-ac", "0"], "Apagado de monitor en AC deshabilitado"),
        (["powercfg", "/change", "monitor-timeout-dc", "0"], "Apagado de monitor en DC deshabilitado")
    ]

    for cmd, desc in cmds_to_run:
        try:
            res = subprocess.run(cmd, check=False, capture_output=True, timeout=15, creationflags=_WIN_NO_WINDOW)
            if res.returncode == 0:
                applied.append(desc)
            else:
                failed.append(f"Fallo en: {desc} (code {res.returncode})")
        except Exception as exc:
            failed.append(f"Excepción en {desc}: {exc}")

    # 3. Optimización de red
    if apply_network_power_settings():
        applied.append("Ahorro de energía en adaptadores de red desactivado")
    else:
        warnings.append("No se pudo aplicar ahorro de energía de red (posible falta de permisos de Administrador)")

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
        "warnings": warnings
    }

def setup_firewall_rules(port_range: str = "9000-9200") -> bool:
    """Agrega o actualiza reglas en el firewall para puertos SRT/UDP sin duplicación."""
    if sys.platform != "win32":
        return False

    logger.info(f"Verificando y configurando regla de firewall RTMS_Media_Ports ({port_range})...")
    try:
        # Verificar si la regla ya existe
        check_cmd = ["netsh", "advfirewall", "firewall", "show", "rule", "name=RTMS_Media_Ports"]
        check_res = subprocess.run(check_cmd, check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW)
        if check_res.returncode == 0:
            logger.info("Regla RTMS_Media_Ports ya existente detectada; renovando...")
            subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=RTMS_Media_Ports"],
                           check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW)

        cmd_fw_srt = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            "name=RTMS_Media_Ports", "dir=in", "action=allow",
            "protocol=UDP", f"localport={port_range}", "profile=private"
        ]
        res = subprocess.run(cmd_fw_srt, check=False, capture_output=True, text=True, timeout=15, creationflags=_WIN_NO_WINDOW)
        if res.returncode == 0:
            logger.info("Reglas del Firewall de Windows configuradas exitosamente.")
            return True
        logger.warning(f"netsh retornó código {res.returncode}: {res.stderr}")
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

# Flags para SetThreadExecutionState (Windows)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

def acquire_stay_awake() -> bool:
    """Evita la suspensión automática del sistema mientras RTMS esté operando activamente."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        res = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        )
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

