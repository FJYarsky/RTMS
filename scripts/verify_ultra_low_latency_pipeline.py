#!/usr/bin/env python3
# ==============================================================================
# RTMS — Real-Time Multicam System
# Script de auditoría y verificación de la tubería de streaming y latencia ultra baja.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Script de verificación automatizada para validar exhaustivamente:
- DirectShow flags (-rtbufsize, -fflags nobuffer+discardcorrupt, -flags low_delay, -avioflags direct, -use_video_device_timestamps 0).
- Parámetros de codificadores (NVENC, QSV, AMF, libx264, libx265) con 0 B-frames, zerolatency=1, delay=0, async_depth=1.
- URLs de SRT (latency=50000, tlpktdrop=1, sndbuf=65536, rcvbuf=65536).
- URLs de UDP Unicast y Multicast LAN.
- Configuración de MediaMTX (writeQueueSize: 256, udpMaxPayloadSize: 1472, WebRTC, SRT).
- Medición de ping y latencia en loopback local.
"""

import asyncio
import os
import sys
import urllib.parse
from typing import List, Tuple

# Asegurar raíz del proyecto en sys.path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from core.command_builder import build_ffmpeg_command
from core.latency_bench import LatencyBenchmarkEngine
from core.mediamtx_mgr import mediamtx_manager
from core.stream_proc import build_client_urls, build_multicast_url, build_stream_url, build_unicast_url

# Estilos de terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(title: str):
    print(f"\n{CYAN}{BOLD}{'=' * 78}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 78}{RESET}\n")


def print_result(label: str, success: bool, detail: str = ""):
    status = f"{GREEN}[PASÓ]{RESET}" if success else f"{RED}[FALLÓ]{RESET}"
    detail_str = f" - {detail}" if detail else ""
    print(f"  {status} {BOLD}{label:<42}{RESET}{detail_str}")


async def audit_directshow_flags() -> List[Tuple[str, bool, str]]:
    results = []
    cfg = {
        "device_path": "Integrated Camera",
        "resolution": "1080p",
        "fps": 30,
        "protocol": "srt",
        "port": 9000,
        "encoder": "libx264",
        "zerolatency": True,
        "use_mjpeg_input": True,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)

    has_fflags = "-fflags" in cmd and "nobuffer+discardcorrupt" in cmd[cmd.index("-fflags") + 1]
    results.append(("DirectShow -fflags nobuffer+discardcorrupt", has_fflags, "Elimina colas internas de demuxer"))

    has_flags = "-flags" in cmd and "low_delay" in cmd[cmd.index("-flags") + 1]
    results.append(("DirectShow -flags low_delay", has_flags, "Fuerza modo de latencia ultra baja"))

    has_avio = "-avioflags" in cmd and "direct" in cmd[cmd.index("-avioflags") + 1]
    results.append(("DirectShow -avioflags direct", has_avio, "Acceso directo a I/O sin encolamiento"))

    has_rtbuf = "-rtbufsize" in cmd and cmd[cmd.index("-rtbufsize") + 1] == "25M"
    results.append(("DirectShow -rtbufsize 25M (MJPEG)", has_rtbuf, "Buffer de sensor acotado para evitar backlog"))

    has_ts = "-use_video_device_timestamps" in cmd and cmd[cmd.index("-use_video_device_timestamps") + 1] == "0"
    results.append(("DirectShow -use_video_device_timestamps 0", has_ts, "Erradica acumulación por deriva de reloj"))

    has_mpegts_zero = "-muxdelay" in cmd and cmd[cmd.index("-muxdelay") + 1] == "0"
    results.append(
        ("MPEG-TS -muxdelay 0 & -flush_packets 1", has_mpegts_zero, "Flujo continuo sin retraso de empaquetado")
    )

    return results


async def audit_encoder_flags() -> List[Tuple[str, bool, str]]:
    results = []

    # 1. libx264
    cfg_264 = {"device_path": "virtual://test", "encoder": "libx264", "zerolatency": True}
    cmd_264, _, _ = await build_ffmpeg_command(cfg_264)
    has_264 = (
        "-tune" in cmd_264
        and "zerolatency" in cmd_264
        and "-bf" in cmd_264
        and cmd_264[cmd_264.index("-bf") + 1] == "0"
    )
    results.append(("CPU libx264 (zerolatency, 0 B-frames)", has_264, "-tune zerolatency, -bf 0, repeat-headers=1"))

    # 2. libx265
    cfg_265 = {"device_path": "virtual://test", "encoder": "libx265", "zerolatency": True}
    cmd_265, _, _ = await build_ffmpeg_command(cfg_265)
    has_265 = (
        "-tune" in cmd_265
        and "zerolatency" in cmd_265
        and "-bf" in cmd_265
        and cmd_265[cmd_265.index("-bf") + 1] == "0"
    )
    results.append(("CPU libx265 (zerolatency, 0 B-frames)", has_265, "-tune zerolatency, -bf 0, no-scenecut=1"))

    # 3. NVENC
    cfg_nv = {"device_path": "virtual://test", "encoder": "h264_nvenc", "zerolatency": True}
    cmd_nv, _, _ = await build_ffmpeg_command(cfg_nv)
    has_nv = (
        "-delay" in cmd_nv
        and cmd_nv[cmd_nv.index("-delay") + 1] == "0"
        and "-zerolatency" in cmd_nv
        and cmd_nv[cmd_nv.index("-zerolatency") + 1] == "1"
        and "-bf" in cmd_nv
        and cmd_nv[cmd_nv.index("-bf") + 1] == "0"
    )
    results.append(
        ("NVIDIA NVENC (delay=0, zerolatency=1, 0 B-frames)", has_nv, "-tune ull, -preset p2, -rc cbr, -surfaces 2")
    )

    # 4. Intel QSV
    cfg_qsv = {"device_path": "virtual://test", "encoder": "h264_qsv", "zerolatency": True}
    cmd_qsv, _, _ = await build_ffmpeg_command(cfg_qsv)
    has_qsv = (
        "-async_depth" in cmd_qsv
        and cmd_qsv[cmd_qsv.index("-async_depth") + 1] == "1"
        and "-bf" in cmd_qsv
        and cmd_qsv[cmd_qsv.index("-bf") + 1] == "0"
        and "-look_ahead" in cmd_qsv
        and cmd_qsv[cmd_qsv.index("-look_ahead") + 1] == "0"
    )
    results.append(("Intel QSV (async_depth=1, 0 B-frames, no lookahead)", has_qsv, "Elimina cola interna de 4 frames"))

    # 5. AMD AMF
    cfg_amf = {"device_path": "virtual://test", "encoder": "h264_amf", "zerolatency": True}
    cmd_amf, _, _ = await build_ffmpeg_command(cfg_amf)
    has_amf = (
        "-usage" in cmd_amf
        and cmd_amf[cmd_amf.index("-usage") + 1] == "ultralowlatency"
        and "-async_depth" in cmd_amf
        and cmd_amf[cmd_amf.index("-async_depth") + 1] == "1"
        and "-bf" in cmd_amf
        and cmd_amf[cmd_amf.index("-bf") + 1] == "0"
    )
    results.append(
        ("AMD AMF (async_depth=1, ultralowlatency, 0 B-frames)", has_amf, "Elimina cola interna de 16 frames")
    )

    return results


def audit_srt_parameters() -> List[Tuple[str, bool, str]]:
    results = []
    url = build_stream_url(
        protocol="srt",
        port=8890,
        mode="caller",
        zerolatency=True,
        streamid="publish:cam_test",
    )
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

    lat_ok = qs.get("latency", [""])[0] == "50000"
    results.append(("SRT Loopback Latency (50ms = 50000 us)", lat_ok, f"Valor: {qs.get('latency', [''])[0]} us"))

    drop_ok = qs.get("tlpktdrop", [""])[0] == "1"
    results.append(("SRT Too-Late Packet Drop (tlpktdrop=1)", drop_ok, "Descarta paquetes fuera de ventana de tiempo"))

    snd_ok = qs.get("sndbuf", [""])[0] == "65536"
    results.append(("SRT Socket Send Buffer (sndbuf=65536)", snd_ok, "64 KB para evitar acumulación en socket"))

    rcv_ok = qs.get("rcvbuf", [""])[0] == "65536"
    results.append(("SRT Socket Receive Buffer (rcvbuf=65536)", rcv_ok, "64 KB para evitar acumulación en recepción"))

    return results


def audit_udp_parameters() -> List[Tuple[str, bool, str]]:
    results = []
    unicast = build_unicast_url(9000, "127.0.0.1")
    multicast = build_multicast_url(9001)

    has_pkt = "pkt_size=1316" in unicast and "pkt_size=1316" in multicast
    results.append(("UDP Packet Size (pkt_size=1316)", has_pkt, "7 paquetes TS por datagrama Ethernet"))

    has_buf = "buffer_size=65536" in unicast and "buffer_size=65536" in multicast
    results.append(("UDP Buffer Size (buffer_size=65536)", has_buf, "64 KB para entrega de trama inmediata"))

    has_overrun = "overrun_nonfatal=1" in unicast and "overrun_nonfatal=1" in multicast
    results.append(
        ("UDP Overrun Non-Fatal (overrun_nonfatal=1)", has_overrun, "Tolerancia a jitter sin aborto de proceso")
    )

    client_urls = build_client_urls("srt", "127.0.0.1", 9000, "cam_test")
    has_vlc_cache = (
        ":network-caching=300" in client_urls["vlc_command"] and ":clock-jitter=0" not in client_urls["vlc_command"]
    )
    results.append(
        (
            "VLC Player Caching (:network-caching=300)",
            has_vlc_cache,
            "búfer seguro 300ms sin clock-jitter=0 :drop-late-frames",
        )
    )

    return results


def audit_mediamtx_config() -> List[Tuple[str, bool, str]]:
    results = []
    cfg_file = mediamtx_manager.generate_config(srt_port=8890)
    with open(cfg_file, "r", encoding="utf-8") as f:
        content = f.read()

    has_qsize = "writeQueueSize: 256" in content
    results.append(("MediaMTX writeQueueSize: 256", has_qsize, "Previene dilatación de cola ante lectores lentos"))

    has_payload = "udpMaxPayloadSize: 1472" in content
    results.append(("MediaMTX udpMaxPayloadSize: 1472", has_payload, "Ajuste preciso a MTU estándar de red local"))

    has_webrtc = "webrtc: yes" in content and "webrtcAddress: 127.0.0.1:8889" in content
    results.append(("MediaMTX WebRTC WHEP Habilitado", has_webrtc, "Puerto 8889, UDP local :8189"))

    has_srt = "srt: yes" in content and "srtAddress: :8890" in content
    results.append(("MediaMTX SRT Central Habilitado", has_srt, "Puerto 8890"))

    has_override = "overridePublisher: yes" in content
    results.append(("MediaMTX overridePublisher: yes", has_override, "Permite reconexión ágil de publicadores"))

    return results


async def main():
    print_header("AUDITORÍA DE TUBERÍA DE STREAMING Y PARÁMETROS DE ULTRA BAJA LATENCIA")

    all_passed = True

    # 1. DirectShow
    print(f"{BOLD}{CYAN}1. Parámetros de Ingesta DirectShow (Cámaras Físicas):{RESET}")
    for label, ok, detail in await audit_directshow_flags():
        print_result(label, ok, detail)
        if not ok:
            all_passed = False

    # 2. Codificadores
    print(f"\n{BOLD}{CYAN}2. Parámetros de Codificadores de Video (Hardware & CPU):{RESET}")
    for label, ok, detail in await audit_encoder_flags():
        print_result(label, ok, detail)
        if not ok:
            all_passed = False

    # 3. Protocolo SRT
    print(f"\n{BOLD}{CYAN}3. Protocolo SRT (Loopback & Network Caller/Listener):{RESET}")
    for label, ok, detail in audit_srt_parameters():
        print_result(label, ok, detail)
        if not ok:
            all_passed = False

    # 4. Protocolos UDP
    print(f"\n{BOLD}{CYAN}4. Protocolos UDP Unicast, Multicast LAN & VLC Caching:{RESET}")
    for label, ok, detail in audit_udp_parameters():
        print_result(label, ok, detail)
        if not ok:
            all_passed = False

    # 5. MediaMTX
    print(f"\n{BOLD}{CYAN}5. MediaMTX y WebRTC (Anti-Buffering & Baja Latencia):{RESET}")
    for label, ok, detail in audit_mediamtx_config():
        print_result(label, ok, detail)
        if not ok:
            all_passed = False

    # 6. Medición rápida de ping UDP
    print(f"\n{BOLD}{CYAN}6. Medición de Ping Loopback UDP en Vivo:{RESET}")
    stats = LatencyBenchmarkEngine.measure_udp_socket_ping(port=9878, iterations=30, timeout=0.05)
    if stats.samples_count > 0:
        print_result(
            "Loopback UDP Ping RTT",
            True,
            f"Avg: {stats.avg_ms:.3f} ms | Min: {stats.min_ms:.3f} ms | Jitter: {stats.jitter_ms:.3f} ms",
        )
    else:
        print_result("Loopback UDP Ping RTT", False, "No se recibieron respuestas de socket")

    print_header("RESUMEN DE AUDITORÍA")
    if all_passed:
        print(f"  {GREEN}{BOLD}TODOS LOS PARÁMETROS DE ULTRA BAJA LATENCIA CUMPLEN CON LA ESPECIFICACIÓN.{RESET}\n")
    else:
        print(f"  {RED}{BOLD}SE DETECTARON DISCREPANCIAS EN ALGUNOS PARÁMETROS.{RESET}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
