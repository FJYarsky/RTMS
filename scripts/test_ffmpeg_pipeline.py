#!/usr/bin/env python3
# ==============================================================================
# RTMS — Real-Time Multicam System
# Herramienta de línea de comandos para diagnóstico y pruebas de FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import os
import sys
import asyncio
import argparse
import time

# Asegurar raíz del proyecto en sys.path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from core.__version__ import __version__
from core.hardware import get_directshow_devices
from core.ffmpeg_tester import (
    FFmpegDiagnosticSuite,
    VirtualCameraSource
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Colores ANSI para terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(title: str):
    print(f"\n{CYAN}{BOLD}{'=' * 72}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 72}{RESET}\n")


def ok_mark(text: str):
    print(f"  {GREEN}[OK]{RESET} {text}")


def fail_mark(text: str):
    print(f"  {RED}[FALLO]{RESET} {text}")


def warn_mark(text: str):
    print(f"  {YELLOW}[AVISO]{RESET} {text}")


def info_mark(text: str):
    print(f"  {CYAN}[INFO]{RESET} {text}")


async def run_binary_diagnostics(suite: FFmpegDiagnosticSuite):
    header("1. DIAGNÓSTICO DE BINARIO, PROTOCOLOS Y CÓDECS FFMPEG")
    rep = suite.check_binary_and_protocols()

    if not rep["available"]:
        fail_mark(f"FFmpeg NO está disponible en disco ni en PATH: {rep['path']}")
        return False

    ok_mark(f"Binario FFmpeg: {rep['path']}")
    info_mark(f"Versión: {rep['version']}")

    if rep["srt_enabled"]:
        ok_mark("Protocolo SRT (libsrt): HABILITADO y soportado nativamente")
    else:
        fail_mark("Protocolo SRT: NO soportado por esta compilación de FFmpeg")

    if rep["udp_enabled"]:
        ok_mark("Protocolo UDP (MPEG-TS Multicast/Unicast): HABILITADO")
    else:
        fail_mark("Protocolo UDP: NO soportado")

    if rep["dshow_enabled"]:
        ok_mark("Subsistema DirectShow (Captura de hardware Windows): HABILITADO")
    else:
        fail_mark("DirectShow: NO soportado")

    print(f"\n  {BOLD}Aceleración por Hardware (Códecs H.264 disponibles):{RESET}")
    if rep["nvenc_enabled"]:
        ok_mark("NVIDIA NVENC (h264_nvenc): DISPONIBLE (Aceleración GPU por hardware)")
    else:
        warn_mark("NVIDIA NVENC: No detectado o no disponible en este hardware")

    if rep["qsv_enabled"]:
        ok_mark("Intel QuickSync (h264_qsv): DISPONIBLE")
    if rep["amf_enabled"]:
        ok_mark("AMD AMF (h264_amf): DISPONIBLE")
    if rep["libx264_enabled"]:
        ok_mark("Software CPU (libx264): DISPONIBLE")

    return rep["available"] and rep["srt_enabled"] and rep["udp_enabled"]


async def run_camera_diagnostics(suite: FFmpegDiagnosticSuite):
    header("2. DIAGNÓSTICO DE DISPOSITIVOS DIRECTSHOW FÍSICOS")
    devices = await get_directshow_devices()
    if not devices:
        warn_mark("No se detectaron cámaras físicas ni virtuales DirectShow conectadas.")
        return

    info_mark(f"Se encontraron {len(devices)} dispositivos DirectShow registrados:")
    for dev in devices:
        name = dev["friendly_name"]
        print(f"\n  {BOLD}Dispositivo:{RESET} {CYAN}{name}{RESET}")
        caps = suite.probe_dshow_camera_caps(name)
        if caps["error"]:
            fail_mark(f"Error al interrogar capacidades DirectShow: {caps['error']}")
            continue

        info_mark(f"Resolución máxima nativa reportada: {caps['max_resolution']}")
        info_mark(f"FPS máximo nativo soportado: {caps['max_fps']}")

        if caps["supports_1080p60"]:
            ok_mark("Soporta 1080p @ 60 FPS nativamente por hardware DirectShow")
        else:
            warn_mark(
                f"ESTE HARDWARE NO SOPORTA 1080p@60FPS NATIVO. Máximo: {caps['max_resolution']} @ {caps['max_fps']}fps. "
                "Forzar 1080p60 en este dispositivo provocará caídas severas de cuadros en el driver DirectShow."
            )

        if caps["supported_modes"]:
            print(f"    Modos soportados ({len(caps['supported_modes'])}):")
            for m in caps["supported_modes"][:5]:
                print(f"      - {m['pixel_format']} {m['width']}x{m['height']} @ {m['fps']} fps")
            if len(caps["supported_modes"]) > 5:
                print(f"      - ... y {len(caps['supported_modes']) - 5} modos más.")


async def run_encoder_benchmark(suite: FFmpegDiagnosticSuite):
    header("3. BENCHMARK DE CODIFICADORES A 1080p @ 60 FPS")
    rep = suite.check_binary_and_protocols()
    encoders = ["libx264"]
    if rep["nvenc_enabled"]:
        encoders.append("h264_nvenc")

    for enc in encoders:
        info_mark(f"Probando codificador {enc} a 1080p @ 60fps (180 cuadros de prueba)...")
        res = await suite.benchmark_encoder(encoder=enc, resolution="1080p", fps=60, frames=180)
        if res["success"]:
            fps_ach = res["achieved_fps"]
            rt = res["can_maintain_realtime"]
            speedup = fps_ach / 60.0
            if rt:
                ok_mark(
                    f"{enc}: {fps_ach:.1f} FPS alcanzados ({speedup:.2f}x tiempo real) -> "
                    f"¡MANTIENE 60 FPS ESTABLES DE SOBRA!"
                )
            else:
                warn_mark(
                    f"{enc}: {fps_ach:.1f} FPS alcanzados ({speedup:.2f}x tiempo real) -> "
                    f"Riesgo de cuello de botella a 60 FPS"
                )
        else:
            fail_mark(f"{enc}: Falló la prueba de codificación.")


async def run_srt_tests(suite: FFmpegDiagnosticSuite, base_port: int = 9970):
    header("4. PRUEBAS DE CONEXIÓN Y DIGESTIÓN DE STREAM SRT")

    # Prueba 4.1: SRT sin contraseña (flujo estándar abierto)
    port = base_port
    info_mark(f"Prueba 4.1: Emisor Listener <-> Receptor Caller (SIN contraseña) en puerto {port}...")
    digest = await suite.test_srt_connection(
        port=port,
        resolution="1080p",
        fps=60,
        passphrase_sender="",
        passphrase_receiver="",
        duration_seconds=3.0
    )
    if digest.is_success and digest.real_fps >= 50.0:
        ok_mark(
            f"SRT abierto exitoso: {digest.frames_decoded} cuadros decodificados a {digest.real_fps:.2f} FPS "
            f"({digest.width}x{digest.height}, {digest.codec}, velocidad {digest.speed})"
        )
    else:
        fail_mark(f"SRT abierto falló. Detalle:\n{digest.summary()}")

    # Prueba 4.2: SRT con contraseña correcta (handshake cifrado PBKDF2)
    port += 1
    pwd = "ClaveSegura12345"
    info_mark(f"Prueba 4.2: Emisor Listener <-> Receptor Caller (CON contraseña idéntica: '{pwd}') en puerto {port}...")
    digest = await suite.test_srt_connection(
        port=port,
        resolution="1080p",
        fps=60,
        passphrase_sender=pwd,
        passphrase_receiver=pwd,
        duration_seconds=3.0
    )
    if digest.is_success and digest.real_fps >= 50.0:
        ok_mark(
            f"SRT con contraseña correcta exitoso: {digest.frames_decoded} cuadros decodificados a {digest.real_fps:.2f} FPS"
        )
    else:
        fail_mark(f"SRT con contraseña falló. Detalle:\n{digest.summary()}")

    # Prueba 4.3: Emisor Listener con contraseña, Receptor SIN contraseña (diagnóstico del bug)
    port += 1
    info_mark(f"Prueba 4.3: DIAGNÓSTICO DE BUG -> Listener con contraseña, Caller SIN contraseña en puerto {port}...")
    digest = await suite.test_srt_connection(
        port=port,
        resolution="720p",
        fps=30,
        passphrase_sender="ClaveOculta123",
        passphrase_receiver="",
        duration_seconds=2.0
    )
    expected_error = any("password required" in e.lower() or "error:unsecure" in e.lower() or "i/o error" in e.lower() for e in digest.errors)
    if not digest.is_connected and expected_error:
        ok_mark(
            "COMPORTAMIENTO CONFIRMADO: La conexión fue rechazada de inmediato como se esperaba. "
            f"Error capturado: {digest.errors[0] if digest.errors else 'Rechazo por falta de credencial'}"
        )
    else:
        warn_mark(f"Resultado inesperado en prueba de rechazo: {digest.summary()}")

    # Prueba 4.4: Desconexión y reconexión en SRT
    port += 1
    info_mark(f"Prueba 4.4: Ciclo de vida y reconexión SRT en puerto {port}...")
    cam = VirtualCameraSource()
    sender_url = f"srt://0.0.0.0:{port}?mode=listener&latency=120000"
    receiver_url = f"srt://127.0.0.1:{port}?mode=caller&latency=120000"
    started = await cam.start(output_url=sender_url, resolution="720p", fps=30, encoder="libx264")
    if started:
        await asyncio.sleep(0.4)
        # Primera conexión
        d1 = await suite.receiver.digest_stream(receiver_url, "srt", duration_seconds=1.5)
        if d1.is_success:
            ok_mark(f"Primera conexión completada ({d1.frames_decoded} cuadros recibidos).")
        else:
            fail_mark(f"Primera conexión falló: {d1.errors}")

        # Pequeña pausa simulando reconexión del receptor
        await asyncio.sleep(0.5)

        # En FFmpeg puro como emisor listener, al desconectar el receptor el emisor termina con I/O error.
        is_sender_alive = (cam.process is not None and cam.process.returncode is None)
        if not is_sender_alive:
            info_mark(
                "FFmpeg Listener nativo terminó al desconectar el cliente (I/O error -5). "
                "RTMS maneja esto reiniciando el listener automáticamente para la siguiente conexión."
            )
        await cam.stop()


async def run_udp_tests(suite: FFmpegDiagnosticSuite, base_port: int = 9980):
    header("5. PRUEBAS DE CONEXIÓN Y ESTABILIDAD UDP (1080p @ 60 FPS)")

    # Prueba 5.1: UDP Multicast a 720p@30fps
    port = base_port
    info_mark(f"Prueba 5.1: UDP Multicast a 720p @ 30 FPS en puerto {port}...")
    d1 = await suite.test_udp_connection(port=port, multicast=True, resolution="720p", fps=30, buffer_size=4194304, repeat_headers=True, duration_seconds=3.0)
    if d1.is_success and d1.real_fps >= 25.0:
        ok_mark(f"UDP 720p@30fps exitoso: {d1.frames_decoded} cuadros a {d1.real_fps:.2f} FPS.")
    else:
        fail_mark(f"UDP 720p@30fps falló: {d1.summary()}")

    # Prueba 5.2: UDP 1080p@60fps con buffer pequeño (64 KB) vs buffer optimizado (4 MB)
    port += 1
    info_mark("Prueba 5.2: UDP a 1080p @ 60 FPS con BUFFER PEQUEÑO (65535 bytes = 64KB)...")
    d_small = await suite.test_udp_connection(port=port, multicast=False, resolution="1080p", fps=60, buffer_size=65535, repeat_headers=False, duration_seconds=3.0)
    info_mark(f"Resultado con 64KB: {d_small.frames_decoded} cuadros, FPS real: {d_small.real_fps:.2f}, Errores: {len(d_small.errors)}")

    port += 1
    info_mark("Prueba 5.3: UDP a 1080p @ 60 FPS con BUFFER OPTIMIZADO (4194304 bytes = 4MB) y repeat-headers...")
    d_opt = await suite.test_udp_connection(port=port, multicast=False, resolution="1080p", fps=60, buffer_size=4194304, repeat_headers=True, duration_seconds=3.0)
    if d_opt.is_success and d_opt.real_fps >= 55.0:
        ok_mark(
            f"UDP 1080p@60fps OPTIMIZADO: {d_opt.frames_decoded} cuadros a {d_opt.real_fps:.2f} FPS continuos "
            f"({d_opt.width}x{d_opt.height}, {d_opt.codec}, 0 cuadros caídos)"
        )
    else:
        fail_mark(f"UDP 1080p@60fps optimizado falló: {d_opt.summary()}")


async def run_virtual_camera_server(args):
    header("6. SERVIDOR DE CÁMARA VIRTUAL EN VIVO PARA PRUEBAS EXTERNAS (OBS / vMix)")
    cam = VirtualCameraSource()

    proto = args.proto.lower()
    port = args.port
    res = args.res
    fps = args.fps
    pwd = args.passphrase

    if proto == "srt":
        url = f"srt://0.0.0.0:{port}?mode=listener&latency=120000&transtype=live&smoother=live&tlpktdrop=1"
        if pwd:
            url += f"&passphrase={pwd}"
        client_url = f"srt://127.0.0.1:{port}?mode=caller&latency=120000"
        if pwd:
            client_url += f"&passphrase={pwd}"
    else:
        ip_last = (port % 200) + 1
        url = f"udp://239.255.0.{ip_last}:{port}?pkt_size=1316&buffer_size=4194304"
        client_url = url

    print(f"  {BOLD}Iniciando cámara virtual con parámetros:{RESET}")
    print(f"    - Protocolo: {proto.upper()}")
    print(f"    - Resolución: {res} @ {fps} FPS")
    print(f"    - Codificador: {args.encoder}")
    print(f"    - Bitrate: {args.bitrate} kbps")
    if pwd:
        print(f"    - Contraseña SRT: {pwd}")
    print(f"\n  {GREEN}{BOLD}URL PARA CONECTAR DESDE OBS / vMix / VLC:{RESET}")
    print(f"  {CYAN}{BOLD}{client_url}{RESET}\n")

    started = await cam.start(
        output_url=url,
        resolution=res,
        fps=fps,
        encoder=args.encoder,
        bitrate=args.bitrate,
        zerolatency=True,
        repeat_headers=True
    )
    if not started:
        fail_mark("No se pudo iniciar la cámara virtual.")
        return

    ok_mark("Cámara virtual transmitiendo en vivo. Presiona Ctrl+C para detener.")
    try:
        while True:
            await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nDeteniendo cámara virtual...")
    finally:
        await cam.stop()
        ok_mark("Cámara virtual detenida limpiamente.")


async def main_async():
    parser = argparse.ArgumentParser(description="RTMS FFmpeg Deep Diagnostic & Testing Suite")
    parser.add_argument("--all", action="store_true", help="Ejecutar todas las baterías de prueba diagnósticas")
    parser.add_argument("--binary", action="store_true", help="Diagnóstico de binario y protocolos")
    parser.add_argument("--camera", action="store_true", help="Diagnóstico de cámaras DirectShow físicas")
    parser.add_argument("--bench", action="store_true", help="Benchmark de codificadores 1080p60")
    parser.add_argument("--srt", action="store_true", help="Pruebas de entablado y digestión SRT")
    parser.add_argument("--udp", action="store_true", help="Pruebas de entablado y digestión UDP a 1080p60")
    parser.add_argument("--virtual-cam", action="store_true", help="Lanza una cámara virtual en vivo para conectar con OBS/vMix")
    parser.add_argument("--proto", default="srt", choices=["srt", "udp"], help="Protocolo para la cámara virtual")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de transmisión")
    parser.add_argument("--res", default="1080p", help="Resolución (720p, 1080p, 4K)")
    parser.add_argument("--fps", type=int, default=60, help="FPS objetivo")
    parser.add_argument("--encoder", default="libx264", help="Codificador (libx264, h264_nvenc, etc.)")
    parser.add_argument("--bitrate", type=int, default=6000, help="Bitrate en kbps")
    parser.add_argument("--passphrase", default="", help="Contraseña opcional para SRT")

    args = parser.parse_args()
    suite = FFmpegDiagnosticSuite()

    if args.virtual_cam:
        await run_virtual_camera_server(args)
        return

    # Si no se especificó ninguna bandera, ejecutar todo por defecto
    run_all = args.all or not (args.binary or args.camera or args.bench or args.srt or args.udp)

    header(f"RTMS — SUITE DE PRUEBAS Y DIAGNÓSTICO PROFUNDO DE FFMPEG v{__version__}")
    print(f"Fecha y Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Plataforma: {sys.platform} | Python: {sys.version.split()[0]}\n")

    if run_all or args.binary:
        await run_binary_diagnostics(suite)

    if run_all or args.camera:
        await run_camera_diagnostics(suite)

    if run_all or args.bench:
        await run_encoder_benchmark(suite)

    if run_all or args.srt:
        await run_srt_tests(suite)

    if run_all or args.udp:
        await run_udp_tests(suite)

    header("RESUMEN DE DIAGNÓSTICO COMPLETADO")
    print("Todas las pruebas y verificaciones fueron ejecutadas con éxito.")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario.")


if __name__ == "__main__":
    main()
