# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.2
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import subprocess
import logging
import sys
import os
import re
import json
import winreg

logger = logging.getLogger("rtms.system_env")

_WIN_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKUP_FILE = os.path.join(get_base_dir(), "config", "power_backup.json")

def get_net_adapters_pnp():
    """Obtiene los valores actuales de PnPCapabilities para todos los adaptadores de red."""
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
    path = r"SYSTEM\CurrentControlSet\Control\Power"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            val, _ = winreg.QueryValueEx(key, "HibernateEnabled")
            return val
    except Exception:
        return 1

def get_power_setting(subgroup: str, setting: str):
    """Consulta los índices actuales de AC y DC para una configuración de energía de forma silenciosa."""
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

def get_active_scheme_guid():
    """Obtiene el GUID del plan de energía activo actual sin ventanas de consola."""
    res = subprocess.run(
        ["powercfg", "-getactivescheme"],
        capture_output=True, text=True, check=False,
        creationflags=_WIN_NO_WINDOW
    )
    match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', res.stdout)
    if match:
        return match.group(0)
    return "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" # Default fallback Alto rendimiento

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

def apply_network_power_settings():
    """Desactiva el ahorro de energía en todos los adaptadores de red y Wake-on-LAN sin mostrar ventanas."""
    if sys.platform != "win32":
        return
    
    logger.info("Configurando adaptadores de red para máximo rendimiento...")
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
    
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_1], capture_output=True, text=True, check=False, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd_2], capture_output=True, text=True, check=False, creationflags=_WIN_NO_WINDOW)
        logger.info("Ahorro de energía en adaptadores de red desactivado exitosamente.")
    except Exception as e:
        logger.warning(f"No se pudo desactivar el ahorro de energía de los adaptadores de red: {e}")

def restore_original_power_settings():
    """Restaura la configuración de energía y red a su estado original previo a la optimización."""
    if sys.platform != "win32":
        return {"status": "error", "message": "No en Windows"}
        
    if not os.path.exists(BACKUP_FILE):
        return {"status": "error", "message": "No se encontró respaldo original de energía"}
        
    logger.info("Restaurando configuraciones originales de energía...")
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            backup = json.load(f)
            
        active_guid = backup.get("active_scheme_guid")
        if active_guid:
            subprocess.run(["powercfg", "-setactive", active_guid], check=False, creationflags=_WIN_NO_WINDOW)
            
        timeouts = backup.get("timeouts", {})
        
        def restore_val(subgroup, setting, ac_key, dc_key):
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
        except Exception:
            pass
            
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
            except Exception:
                pass
                
        try:
            os.remove(BACKUP_FILE)
        except OSError:
            pass
            
        logger.info("Configuración original restaurada completamente.")
        return {"status": "ok", "message": "Restauración completada con éxito"}
    except Exception as e:
        logger.error(f"Error durante la restauración energética: {e}")
        return {"status": "error", "message": f"Error: {e}"}

def setup_windows_environment():
    """Configura de forma 100% silenciosa el entorno de Windows para máxima estabilidad."""
    if sys.platform != "win32":
        return

    backup_current_power_settings()

    logger.info("Aplicando optimizaciones de estabilidad y energía en Windows...")
    try:
        subprocess.run(["powercfg", "-setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        
        active_guid = get_active_scheme_guid()
        subprocess.run(["powercfg", "-setacvalueindex", active_guid, "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "-setdcvalueindex", active_guid, "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "-setactive", active_guid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)

        subprocess.run(["powercfg", "/change", "standby-timeout-ac", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/change", "standby-timeout-dc", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/hibernate", "off"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/change", "disk-timeout-ac", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/change", "disk-timeout-dc", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/change", "monitor-timeout-ac", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        subprocess.run(["powercfg", "/change", "monitor-timeout-dc", "0"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)

        apply_network_power_settings()

    except Exception as e:
        logger.error(f"Error al aplicar optimizaciones energéticas: {e}")

def setup_firewall_rules():
    """Agrega reglas al firewall para puertos SRT, UDP y FastAPI de forma silenciosa."""
    if sys.platform != "win32":
        return
        
    logger.info("Configurando reglas del firewall en Windows...")
    try:
        cmd_fw_srt = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            "name=RTMS_Media_Ports", "dir=in", "action=allow",
            "protocol=UDP", "localport=9000-9200", "profile=private"
        ]
        subprocess.run(cmd_fw_srt, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_WIN_NO_WINDOW)
        logger.info("Reglas del Firewall de Windows configuradas exitosamente.")
    except Exception as e:
        logger.error(f"Error al configurar firewall: {e}")
