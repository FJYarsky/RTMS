# ==============================================================================
# RTMS v2.2.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

"""Herramienta de diagnóstico integral CLI (RTMS Doctor)."""

import os
import sys
import socket
import asyncio
import platform
import subprocess

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

from core.__version__ import __version__
from core.port_mgr import port_manager
from core.config_mgr import load_config
from core.hardware import get_directshow_devices, get_ffmpeg_bin, has_ffmpeg_binary, _FFMPEG_BIN

def check_os() -> bool:
    is_win = platform.system() == "Windows"
    rel = platform.release()
    print(f"[{'OK' if is_win else 'FAIL'}] Sistema Operativo: {platform.system()} {rel} ({platform.architecture()[0]})")
    return is_win

def check_ffmpeg_binary() -> bool:
    ffmpeg_exe = get_ffmpeg_bin()
    if not has_ffmpeg_binary():
        print(f"[FAIL] FFmpeg: No encontrado en {_FFMPEG_BIN} ni en PATH del sistema")
        return False
    try:
        res = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True, timeout=5)
        first_line = res.stdout.splitlines()[0] if res.stdout else "Versión desconocida"
        print(f"[OK] FFmpeg ({ffmpeg_exe}): {first_line}")
        return True
    except Exception as e:
        print(f"[FAIL] FFmpeg: Error al ejecutar: {e}")
        return False

def check_srt_support() -> bool:
    ffmpeg_exe = get_ffmpeg_bin()
    if not has_ffmpeg_binary():
        print("[FAIL] Protocolo SRT: FFmpeg ausente")
        return False
    try:
        res = subprocess.run([ffmpeg_exe, "-protocols"], capture_output=True, text=True, timeout=5)
        has_srt = "srt" in res.stdout.lower()
        print(f"[{'OK' if has_srt else 'FAIL'}] Protocolo SRT: {'Habilitado' if has_srt else 'No soportado por el build'}")
        return has_srt
    except Exception:
        print("[FAIL] Protocolo SRT: Error al consultar protocolos")
        return False

async def check_gpu_encoders() -> bool:
    if not has_ffmpeg_binary():
        print("[FAIL] GPU Encoders: FFmpeg ausente")
        return False

    from core.hardware import hardware_detector
    found = await hardware_detector.get_available_encoders()
    hw_only = [e for e in found if e != "libx264"]

    if hw_only:
        print(f"[OK] GPU Hardware Encoders: {', '.join(hw_only)}")
        return True
    else:
        print("[WARN] GPU Hardware Encoders: Ninguno detectado (Se utilizará CPU libx264)")
        return True  # Fallback viable

async def check_directshow_cameras() -> bool:
    devices = await get_directshow_devices()
    if devices:
        names = [d["friendly_name"] for d in devices]
        print(f"[OK] Dispositivos DirectShow ({len(devices)}): {', '.join(names)}")
        return True
    else:
        print("[WARN] Dispositivos DirectShow: No se detectaron cámaras conectadas en este momento")
        return True

def check_network_ip() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        print(f"[OK] Red LAN (IP de Emisión): {ip}")
        return True
    except Exception:
        print("[WARN] Red LAN: Sin conexión externa (Utilizando 127.0.0.1)")
        return True

def check_media_ports() -> bool:
    free_count = 0
    for p in range(9000, 9010):
        if not port_manager.is_port_in_use(p):
            free_count += 1
    if free_count > 0:
        print(f"[OK] Puertos Multimedia: Disponibles en rango 9000-9200 ({free_count}/10 libres en segmento inicial)")
        return True
    else:
        print("[FAIL] Puertos Multimedia: Rango 9000-9010 bloqueado u ocupado por otros procesos")
        return False

def check_config_storage() -> bool:
    try:
        cfg = load_config()
        cams_count = len(cfg.get("cameras", {}))
        print(f"[OK] Configuración: Legible (Versión {cfg.get('version')}, {cams_count} cámaras registradas)")
        return True
    except Exception as e:
        print(f"[FAIL] Configuración: Error al leer: {e}")
        return False

async def run_doctor() -> bool:
    print("=" * 60)
    print(f" RTMS Doctor — Herramienta de Diagnóstico v{__version__}")
    print("=" * 60)

    checks = [
        ("Sistema Operativo", check_os()),
        ("Binario FFmpeg", check_ffmpeg_binary()),
        ("Protocolo SRT", check_srt_support()),
        ("Aceleración GPU", await check_gpu_encoders()),
        ("Cámaras DirectShow", await check_directshow_cameras()),
        ("Red Local", check_network_ip()),
        ("Puertos Media", check_media_ports()),
        ("Almacenamiento Config", check_config_storage()),
    ]

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)

    print("=" * 60)
    success = (passed == total)
    if success:
        print(f"RTMS Doctor: {passed}/{total} verificaciones aprobadas. ¡Sistema listo para producción!")
    else:
        print(f"RTMS Doctor: {passed}/{total} verificaciones aprobadas. Revisa las advertencias o fallos anteriores.")
    print("=" * 60)
    return success

if __name__ == "__main__":
    ok = asyncio.run(run_doctor())
    sys.exit(0 if ok else 1)
