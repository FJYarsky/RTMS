#!/usr/bin/env python3
# ==============================================================================
# RTMS — Real-Time Multicam System
# CLI de Verificación E2E de Cadena de Ejecución, Diagnóstico y Medición de Ping
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Herramienta CLI de diagnóstico integral y certificación ineludible de la cadena de ejecución.
Prueba de forma local e inflanqueable todos los protocolos (SRT, UDP, WebRTC),
modos de cámara (virtual con reloj quemado, virtual testsrc, hardware DirectShow),
detecta cuelgues, fallos de pipeline, artefactos y calcula el ping/latencia matemática.
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from typing import List

# Asegurar raíz del proyecto en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


from core.__version__ import __version__
from core.mediamtx_mgr import mediamtx_manager
from core.pipeline_verifier import (
    CorePipelineVerifier,
    TestResult,
    VirtualClockStreamer,
)

# Colores ANSI para terminal
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RESET = "\033[0m"


def print_banner():
    print(
        f"\n{CLR_BOLD}{CLR_CYAN}================================================================================{CLR_RESET}"
    )
    print(
        f"{CLR_BOLD}{CLR_CYAN}RTMS v{__version__} — VERIFICADOR INELUDIBLE DE CADENA DE EJECUCIÓN Y BENCHMARK E2E{CLR_RESET}"
    )
    print(
        f"{CLR_BOLD}{CLR_CYAN}================================================================================{CLR_RESET}"
    )
    print(f"{CLR_DIM}Diagnóstico local de núcleo, protocolos, artefactos y medición de ping/latencia{CLR_RESET}\n")


def print_table(results: List[TestResult]):
    header = f"{'PRUEBA / COMPONENTE':<35} | {'PROTO':<10} | {'ENCODER':<10} | {'ESTADO':<8} | {'PING (AVG)':<10} | {'DETALLES'}"
    divider = "-" * 115
    print("\n" + divider)
    print(f"{CLR_BOLD}{header}{CLR_RESET}")
    print(divider)

    pass_count = 0
    fail_count = 0

    for r in results:
        status_color = CLR_GREEN if r.status == "PASS" else CLR_RED
        status_str = f"{status_color}{CLR_BOLD}[{r.status}]{CLR_RESET}"
        ping_str = f"{r.ping_avg_ms:.1f} ms" if r.ping_avg_ms is not None else "N/A"
        enc_str = r.encoder if r.encoder else "auto"
        print(f"{r.name:<35} | {r.protocol:<10} | {enc_str:<10} | {status_str:<17} | {ping_str:<10} | {r.details}")
        if r.status == "PASS":
            pass_count += 1
        else:
            fail_count += 1

    print(divider)
    total = len(results)
    print(
        f"\n{CLR_BOLD}RESUMEN GENERAL: {CLR_GREEN}{pass_count} EXITOSAS{CLR_RESET} | {CLR_RED}{fail_count} FALLIDAS{CLR_RESET} de {total} pruebas ejecutadas."
    )
    if fail_count == 0:
        print(f"{CLR_BOLD}{CLR_GREEN}ESTADO DE LA CADENA DE EJECUCIÓN: 100% OPERATIVA Y SALUDABLE.{CLR_RESET}\n")
    else:
        print(f"{CLR_BOLD}{CLR_RED}SE DETECTARON FALLOS EN LA CADENA DE EJECUCIÓN. REVISAR DETALLES.{CLR_RESET}\n")


async def run_obs_mode(protocol: str = "srt", port: int = 8890, encoder: str = "libx264"):
    """Mantiene la cámara virtual con reloj quemado en emisión continua para inspección visual en OBS/VLC."""
    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== MODO OBS STUDIO / VLC EN VIVO (Presiona Ctrl+C para salir) ==={CLR_RESET}")
    cam_id = "latency_clock"

    if protocol == "srt":
        await mediamtx_manager.start(srt_port=port)
        pub_url = f"srt://127.0.0.1:{port}?streamid=publish:{cam_id}&mode=caller&latency=10000&tlpktdrop=1&rcvbuf=16384"
        read_url = f"srt://127.0.0.1:{port}?streamid=read:{cam_id}&latency=15000&rcvbuf=16384&tlpktdrop=1"
        vlc_cmd = f'vlc.exe "{read_url}" :network-caching=15 :clock-jitter=0 :clock-synchro=0'
    else:
        port = 9028
        pub_url = f"udp://127.0.0.1:{port}?pkt_size=1316&buffer_size=16384"
        read_url = f"udp://@:{port}?buffer_size=16384&overrun_nonfatal=1"
        vlc_cmd = f'vlc.exe "{read_url}" :network-caching=15'

    print(f"\n{CLR_CYAN}Iniciando transmisión de reloj virtual quemado a 60 FPS ({encoder})...{CLR_RESET}")
    streamer = VirtualClockStreamer(pub_url, fps=60, encoder=encoder)
    streamer.start()

    print(f"\n{CLR_BOLD}INSTRUCCIONES DE CONEXIÓN EN OBS STUDIO:{CLR_RESET}")
    print(f"  1. Añade una {CLR_BOLD}Fuente multimedia{CLR_RESET} (Media Source).")
    print(f"  2. Desmarca {CLR_YELLOW}'Archivo local'{CLR_RESET}.")
    print(f"  3. En Entrada pega: {CLR_GREEN}{read_url}{CLR_RESET}")
    if protocol == "srt":
        print(f"  4. Formato de entrada: {CLR_GREEN}mpegts{CLR_RESET}")
        print(f"  5. {CLR_BOLD}Búfer de red (Network Buffering):{CLR_RESET} reduce a {CLR_GREEN}1 MB{CLR_RESET} o 0.")
    print(f"\n{CLR_BOLD}INSTRUCCIONES PARA VLC MEDIA PLAYER:{CLR_RESET}")
    print(f"  Ejecuta en terminal: {CLR_GREEN}{vlc_cmd}{CLR_RESET}")
    print(
        f"\n{CLR_DIM}El cronómetro muestra milisegundos reales. Coloca la ventana junto a OBS/VLC para comparar el delay.{CLR_RESET}\n"
    )

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n{CLR_YELLOW}Deteniendo emisión de reloj virtual...{CLR_RESET}")
    finally:
        streamer.stop()
        if protocol == "srt":
            mediamtx_manager.stop()


async def main_async():
    parser = argparse.ArgumentParser(
        description="RTMS — Verificador Integral de Cadena de Ejecución, Diagnóstico y Medición de Ping E2E"
    )
    parser.add_argument("--all", action="store_true", help="Ejecuta la suite completa de protocolos, modos y hardware.")
    parser.add_argument(
        "--ping", action="store_true", help="Ejecuta únicamente el benchmark de ping con reloj quemado."
    )
    parser.add_argument(
        "--protocol",
        choices=["all", "srt", "srt_crypt", "udp_mcast", "udp_ucast", "webrtc"],
        default="all",
        help="Protocolo específico a verificar.",
    )
    parser.add_argument(
        "--encoder", choices=["auto", "libx264", "libx265", "nvenc"], default="libx264", help="Codificador a probar."
    )
    parser.add_argument(
        "--obs-mode",
        action="store_true",
        help="Emite el reloj virtual continuamente para prueba manual en OBS Studio / VLC.",
    )
    parser.add_argument("--frames", type=int, default=40, help="Cantidad de cuadros a analizar para medición de ping.")
    parser.add_argument("--json", type=str, help="Ruta de archivo para exportar reporte en formato JSON.")
    parser.add_argument("--markdown", type=str, help="Ruta de archivo para exportar reporte en formato Markdown.")
    parser.add_argument("--port", type=int, default=8890, help="Puerto central SRT de MediaMTX.")

    args = parser.parse_args()
    print_banner()

    if args.obs_mode:
        await run_obs_mode(
            protocol=args.protocol if args.protocol in ("srt", "udp") else "srt",
            port=args.port,
            encoder=args.encoder,
        )
        return 0

    verifier = CorePipelineVerifier(mediamtx_port=args.port)
    results: List[TestResult] = []

    if args.ping:
        print(f"{CLR_CYAN}Ejecutando medición de ping con reloj sintético quemado ({args.encoder})...{CLR_RESET}")
        await verifier.verify_mediamtx_lifecycle()
        r_srt = verifier.verify_burned_in_clock_ping("srt", args.encoder, target_frames=args.frames)
        r_udp = verifier.verify_burned_in_clock_ping("udp", args.encoder, target_frames=args.frames)
        results = [r_srt, r_udp]
        mediamtx_manager.stop()
    elif args.all or args.protocol == "all":
        print(f"{CLR_CYAN}Ejecutando suite completa de diagnóstico de la cadena de ejecución...{CLR_RESET}")
        results = await verifier.run_full_suite()
        mediamtx_manager.stop()
    else:
        # Pruebas individuales según argumento
        print(f"{CLR_CYAN}Ejecutando prueba del protocolo: {args.protocol.upper()}...{CLR_RESET}")
        await verifier.verify_mediamtx_lifecycle()
        if args.protocol == "srt":
            results.append(await verifier.verify_srt_unencrypted(args.encoder))
            results.append(verifier.verify_burned_in_clock_ping("srt", args.encoder, target_frames=args.frames))
        elif args.protocol == "srt_crypt":
            results.append(await verifier.verify_srt_encrypted())
        elif args.protocol == "udp_mcast":
            results.append(await verifier.verify_udp_multicast())
        elif args.protocol == "udp_ucast":
            results.append(await verifier.verify_udp_unicast())
            results.append(verifier.verify_burned_in_clock_ping("udp", args.encoder, target_frames=args.frames))
        elif args.protocol == "webrtc":
            results.append(await verifier.verify_webrtc_whep())
        mediamtx_manager.stop()

    print_table(results)

    # Exportación opcional de reportes
    if args.json:
        data = [asdict(r) for r in results]
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Reporte JSON guardado en: {args.json}")

    if args.markdown:
        lines = [
            f"# RTMS v{__version__} — Reporte de Verificación de Cadena de Ejecución",
            f"**Fecha y Hora:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "| Prueba | Protocolo | Encoder | Estado | Ping Promedio | Detalles |",
            "| :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for r in results:
            ping_str = f"{r.ping_avg_ms} ms" if r.ping_avg_ms else "—"
            lines.append(f"| {r.name} | {r.protocol} | {r.encoder} | {r.status} | {ping_str} | {r.details} |")
        lines.append("")
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Reporte Markdown guardado en: {args.markdown}")

    has_failures = any(r.status == "FAIL" for r in results)
    return 1 if has_failures else 0


def main():
    try:
        code = asyncio.run(main_async())
        sys.exit(code)
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        sys.exit(130)


if __name__ == "__main__":
    main()
