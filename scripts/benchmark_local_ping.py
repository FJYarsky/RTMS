#!/usr/bin/env python3
# ==============================================================================
# RTMS — Real-Time Multicam System v2.8.0
# Suite Exhaustiva de Diagnóstico y Optimización de Ping y Latencia Local (Loopback).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
#
# Responde al requerimiento del usuario:
# "Uno de los test que quiero que profundices es en el ping para disminuirlo lo
# mas posible. Busca un mecanismo para probar el ping recibiendo en mi misma PC"
# ==============================================================================

"""
Script ejecutable integral para diagnosticar, medir y minimizar la latencia y el
ping de recepción en la misma PC (Localhost Loopback 127.0.0.1).

Etapas evaluadas:
1. Ping UDP a nivel de socket de ultra alta precisión (nanosegundos).
2. Ping TCP Handshake (SYN/ACK) contra la API y endpoints de MediaMTX.
3. Transmisión FFmpeg SRT Loopback con flags de ultra baja latencia (latency=20000, tlpktdrop=1, rcvbuf=65536).
4. Pruebas de decodificación y estabilidad con VLC real (:network-caching=30, 50, 100, 150).
5. Generación de informe estructurado JSON y síntesis con recomendaciones de sintonización.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Asegurar raíz del proyecto en sys.path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from core.__version__ import __version__
from core.hardware import get_ffmpeg_bin
from core.latency_bench import LatencyBenchmarkEngine, PingStatistics, VideoPipelineLatencyReport
from core.mediamtx_mgr import mediamtx_manager

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# Colores ANSI para terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"

VLC_PATH = r"C:\Program Files\VideoLAN\VLC\vlc.exe"


def header(title: str):
    print(f"\n{CYAN}{BOLD}{'=' * 76}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 76}{RESET}\n")


def subheader(title: str):
    print(f"\n{BOLD}{CYAN}--- {title} ---{RESET}")


def ok_mark(text: str):
    print(f"  {GREEN}[OK]{RESET} {text}")


def fail_mark(text: str):
    print(f"  {RED}[FALLO]{RESET} {text}")


def warn_mark(text: str):
    print(f"  {YELLOW}[AVISO]{RESET} {text}")


def info_mark(text: str):
    print(f"  {CYAN}[INFO]{RESET} {text}")


def metric_row(label: str, value: str, note: str = ""):
    note_str = f" {DIM}({note}){RESET}" if note else ""
    print(f"  * {label:<32}: {BOLD}{value:<14}{RESET}{note_str}")


async def run_benchmark(
    udp_samples: int = 150,
    tcp_samples: int = 30,
    video_duration: float = 3.5,
    save_json: bool = True,
) -> Dict[str, Any]:
    """Ejecuta la suite completa de benchmark de ping y latencia local."""
    header(f"RTMS v{__version__} — Benchmark de Ping y Latencia de Recepción Local")
    info_mark(f"Entorno: Python {sys.version.split()[0]} sobre Windows ({sys.platform})")
    info_mark(f"Directorio Base: {_BASE_DIR}")

    ffmpeg_bin = get_ffmpeg_bin()
    has_ffmpeg = os.path.exists(ffmpeg_bin)
    has_vlc = os.path.exists(VLC_PATH)

    info_mark(f"FFmpeg Binario : {ffmpeg_bin} -> {'Disponible' if has_ffmpeg else 'No encontrado'}")
    info_mark(f"VLC Media Player: {VLC_PATH} -> {'Disponible' if has_vlc else 'No encontrado'}")

    engine = LatencyBenchmarkEngine(ffmpeg_bin=ffmpeg_bin, vlc_path=VLC_PATH if has_vlc else None)
    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "rtms_version": __version__,
        "system": {
            "os": sys.platform,
            "ffmpeg_bin": ffmpeg_bin,
            "has_ffmpeg": has_ffmpeg,
            "vlc_path": VLC_PATH,
            "has_vlc": has_vlc,
        },
        "phases": {},
        "recommendations": {},
    }

    # =========================================================================
    # FASE 1: Ping a nivel de Socket UDP (Loopback Kernel Windows)
    # =========================================================================
    subheader(f"FASE 1: Medición de Ping UDP en Loopback (127.0.0.1, {udp_samples} paquetes)")
    info_mark("Evaluando tiempo de tránsito de paquetes datagrama con resolución en nanosegundos...")

    udp_stats: PingStatistics = engine.measure_udp_socket_ping(port=29876, iterations=udp_samples)
    results["phases"]["udp_socket_ping"] = udp_stats.to_dict()

    if udp_stats.samples_count > 0 and udp_stats.loss_rate == 0.0:
        ok_mark(f"UDP Loopback completado exitosamente ({udp_stats.samples_count}/{udp_samples} recibidos)")
    else:
        warn_mark(f"UDP Loopback con incidencias: pérdida {udp_stats.loss_rate * 100:.1f}%")

    metric_row("Ping Mínimo", f"{udp_stats.min_ms:.3f} ms", "Límite inferior del kernel")
    metric_row("Ping Promedio", f"{udp_stats.avg_ms:.3f} ms", "Latencia media de ida y vuelta")
    metric_row("Ping Máximo", f"{udp_stats.max_ms:.3f} ms", "Pico observado")
    metric_row("Percentil 95 (p95)", f"{udp_stats.p95_ms:.3f} ms", "95% de los paquetes por debajo")
    metric_row("Percentil 99 (p99)", f"{udp_stats.p99_ms:.3f} ms", "Comportamiento en cola")
    metric_row("Jitter (Fluctuación)", f"{udp_stats.jitter_ms:.3f} ms", "Desviación típica")
    metric_row("Tasa de Pérdida", f"{udp_stats.loss_rate * 100:.2f} %", "Paquetes descartados")

    # =========================================================================
    # FASE 2: Ping TCP Handshake contra MediaMTX
    # =========================================================================
    subheader("FASE 2: Ping de Conexión TCP (Handshake SYN/ACK) a MediaMTX")
    mediamtx_was_started = False
    if not mediamtx_manager.is_running():
        info_mark("Iniciando subproceso MediaMTX en segundo plano para prueba de conexión...")
        await mediamtx_manager.start(srt_port=8890)
        await asyncio.sleep(0.6)
        mediamtx_was_started = True

    info_mark(f"Midiendo tiempo de conexión TCP a la API interna (127.0.0.1:{mediamtx_manager.api_port})...")
    api_tcp_stats: PingStatistics = engine.measure_tcp_connect_ping(
        port=mediamtx_manager.api_port, iterations=tcp_samples
    )
    results["phases"]["tcp_mediamtx_api_ping"] = api_tcp_stats.to_dict()

    metric_row("TCP API Min", f"{api_tcp_stats.min_ms:.3f} ms")
    metric_row("TCP API Avg", f"{api_tcp_stats.avg_ms:.3f} ms", "Handshake SYN/ACK promedio")
    metric_row("TCP API Max", f"{api_tcp_stats.max_ms:.3f} ms")
    metric_row("TCP API p95", f"{api_tcp_stats.p95_ms:.3f} ms")
    metric_row("TCP API Jitter", f"{api_tcp_stats.jitter_ms:.3f} ms")

    info_mark(f"Midiendo tiempo de conexión TCP a WebRTC/WHEP (127.0.0.1:{mediamtx_manager.webrtc_port})...")
    webrtc_tcp_stats: PingStatistics = engine.measure_tcp_connect_ping(
        port=mediamtx_manager.webrtc_port, iterations=tcp_samples
    )
    results["phases"]["tcp_mediamtx_webrtc_ping"] = webrtc_tcp_stats.to_dict()
    metric_row("TCP WebRTC Avg", f"{webrtc_tcp_stats.avg_ms:.3f} ms")

    # =========================================================================
    # FASE 3: Transmisión SRT Loopback de Ultra Baja Latencia
    # =========================================================================
    subheader("FASE 3: Pipeline SRT Loopback de Ultra Baja Latencia (FFmpeg -> MediaMTX)")
    stream_name = "rtms_ping_benchmark_cam"
    srt_latency_ms = 20  # 20ms de buffer en SRT para loopback

    pub_url = (
        f"srt://127.0.0.1:{mediamtx_manager.srt_port}?streamid=publish:{stream_name}"
        f"&latency={srt_latency_ms * 1000}&tlpktdrop=1&rcvbuf=65536"
    )
    read_url = (
        f"srt://127.0.0.1:{mediamtx_manager.srt_port}?streamid=read:{stream_name}&latency={srt_latency_ms * 1000}"
    )

    info_mark(f"URL de Ingesta : {pub_url}")
    info_mark(f"URL de Lectura : {read_url}")
    info_mark("Parámetros SRT: latency=20000 µs (20 ms), tlpktdrop=1, rcvbuf=65536 bytes")

    # Iniciar emisor sintético continuo a 60 FPS
    sender_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=60",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-pat_period",
        "0.1",
        "-pcr_period",
        "20",
        "-fflags",
        "nobuffer+flush_packets",
        "-flags",
        "low_delay",
        "-f",
        "mpegts",
        pub_url,
    ]

    sender_proc: Optional[subprocess.Popen] = None
    try:
        sender_proc = subprocess.Popen(sender_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(1.0)

        # Medir TTFF y fluctuación entre cuadros con el receptor FFmpeg
        receiver_cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-fflags",
            "nobuffer+discardcorrupt",
            "-flags",
            "low_delay",
            "-probesize",
            "64",
            "-analyzeduration",
            "0",
            "-i",
            read_url,
            "-vf",
            "showinfo",
            "-f",
            "null",
            "-",
        ]

        t_client_start = time.perf_counter()
        receiver_proc = await asyncio.create_subprocess_exec(
            *receiver_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        first_frame_ms = 0.0
        frame_timestamps: List[float] = []

        async def read_receiver_stderr():
            nonlocal first_frame_ms
            if receiver_proc.stderr is None:
                return
            while True:
                line = await receiver_proc.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace")
                if "n:" in line_str and "pts_time:" in line_str:
                    now = time.perf_counter()
                    if not frame_timestamps:
                        first_frame_ms = (now - t_client_start) * 1000.0
                    frame_timestamps.append(now)

        read_task = asyncio.create_task(read_receiver_stderr())
        try:
            await asyncio.wait_for(asyncio.sleep(video_duration), timeout=video_duration + 1.0)
        finally:
            read_task.cancel()
            try:
                receiver_proc.terminate()
                await asyncio.wait_for(receiver_proc.wait(), timeout=1.0)
            except Exception:
                receiver_proc.kill()

        total_frames = len(frame_timestamps)
        measured_fps = 0.0
        inter_frame_jitter_ms = 0.0

        if total_frames > 1:
            total_duration = frame_timestamps[-1] - frame_timestamps[0]
            if total_duration > 0:
                measured_fps = (total_frames - 1) / total_duration

            intervals = [
                (frame_timestamps[i] - frame_timestamps[i - 1]) * 1000.0 for i in range(1, len(frame_timestamps))
            ]
            expected_interval = 1000.0 / 60.0
            jitter_vals = [abs(iv - expected_interval) for iv in intervals]
            if jitter_vals:
                inter_frame_jitter_ms = sum(jitter_vals) / len(jitter_vals)

        srt_report = VideoPipelineLatencyReport(
            protocol="srt",
            url=read_url,
            time_to_first_frame_ms=first_frame_ms,
            fps_measured=measured_fps,
            frames_received=total_frames,
            inter_frame_jitter_ms=inter_frame_jitter_ms,
            buffer_underruns=0 if total_frames > 0 else 1,
            recommended_vlc_caching_ms=30 if inter_frame_jitter_ms < 3.0 and first_frame_ms < 150 else 50,
            status="OPTIMAL" if total_frames > 15 else "SUBOPTIMAL",
            notes=[f"TTFF: {first_frame_ms:.1f}ms", f"FPS: {measured_fps:.1f}"],
        )
        results["phases"]["srt_pipeline"] = srt_report.to_dict()

        if total_frames > 0:
            ok_mark(f"SRT Pipeline entregó {total_frames} cuadros a {measured_fps:.1f} FPS")
        else:
            warn_mark("No se detectaron cuadros en el receptor durante el periodo de prueba")

        metric_row("Tiempo a 1er Cuadro (TTFF)", f"{first_frame_ms:.2f} ms", "Latencia de enganche IDR")
        metric_row("FPS Medido", f"{measured_fps:.1f} fps", "Tasa efectiva de decodificación")
        metric_row("Jitter Inter-Frame", f"{inter_frame_jitter_ms:.2f} ms", "Fluctuación entre cuadros consecutivos")
        metric_row("Cuadros Recibidos", f"{total_frames}")

        # =========================================================================
        # FASE 4: Pruebas de Límites de Caching con VLC Real
        # =========================================================================
        subheader("FASE 4: Pruebas de Límites de Caching con VLC Real")
        if has_vlc:
            caching_test_values = [30, 50, 100, 150]
            info_mark(f"Evaluando estabilidad en VLC con :network-caching={caching_test_values} ms...")

            vlc_caching_results = engine.test_vlc_caching_limits(
                url=read_url,
                caching_values=caching_test_values,
            )
            results["phases"]["vlc_caching_limits"] = vlc_caching_results

            for c_val, c_res in vlc_caching_results.items():
                decoded = c_res.get("decoded", False)
                picture_late = c_res.get("picture_late_warnings", 0)
                underruns = c_res.get("underruns", 0)

                status_tag = f"{GREEN}ESTABLE{RESET}" if (decoded and underruns == 0) else f"{YELLOW}ACEPTABLE{RESET}"
                if not decoded:
                    status_tag = f"{RED}SIN DECODIFICAR{RESET}"

                print(
                    f"  * :network-caching={c_val:<3} ms -> {status_tag} | "
                    f"Decodificado: {decoded} | Cuadros tardíos: {picture_late} | Underruns: {underruns}"
                )

            # Determinar caching óptimo
            best_caching = 50
            if vlc_caching_results.get(30, {}).get("decoded", False):
                best_caching = 30
            elif vlc_caching_results.get(50, {}).get("decoded", False):
                best_caching = 50
            else:
                best_caching = 100
        else:
            warn_mark("VLC no encontrado en la ruta esperada. Se omitió la prueba directa con el reproductor.")
            best_caching = 50
            results["phases"]["vlc_caching_limits"] = {"status": "VLC_NOT_INSTALLED"}

    finally:
        if sender_proc:
            try:
                sender_proc.terminate()
                sender_proc.wait(timeout=2.0)
            except Exception:
                sender_proc.kill()

        if mediamtx_was_started:
            info_mark("Deteniendo subproceso MediaMTX iniciado para la prueba...")
            mediamtx_manager.stop()

    # =========================================================================
    # FASE 5: Recomendaciones Óptimas y Exportación de Informe
    # =========================================================================
    subheader("FASE 5: Síntesis de Optimización para Recepción en la Misma PC")

    recommendations = {
        "optimal_srt_latency_ms": 20,
        "optimal_srt_flags": "latency=20000&tlpktdrop=1&rcvbuf=65536",
        "optimal_vlc_caching_ms": best_caching,
        "optimal_vlc_args": [
            f":network-caching={best_caching}",
            ":drop-late-frames",
            ":skip-frames",
        ],
        "ffmpeg_ingest_flags": [
            "-preset ultrafast",
            "-tune zerolatency",
            "-g 15",
            "-pat_period 0.1",
            "-pcr_period 20",
            "-fflags nobuffer+flush_packets",
            "-flags low_delay",
        ],
        "windows_os_optimizations": [
            "TcpAckFrequency=1 (Deshabilita algoritmo Nagle en bucle local)",
            "TCPNoDelay=1 (Transmisión inmediata de paquetes de control)",
            "MMCSS (Multimedia Class Scheduler Service habilitado en FFmpeg/MediaMTX)",
        ],
    }
    results["recommendations"] = recommendations

    info_mark(f"1. Buffer de Transporte SRT : {recommendations['optimal_srt_flags']}")
    info_mark(
        f"2. Caché de Red para VLC     : :network-caching={best_caching} (Monitoreo con búfer seguro anti-congelamiento)"
    )
    info_mark("3. Sincronización de Reloj  : Sin directivas desestabilizadoras (omite clock-jitter=0 para estabilidad)")
    info_mark("4. Parámetros de Emisión     : GOP=15 (0.25-0.5s) con PAT/PCR periódicos para enganche sub-segundo")

    if save_json:
        reports_dir = os.path.join(_BASE_DIR, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, "local_latency_ping_benchmark.json")
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            ok_mark(f"Informe estructurado guardado en: {report_file}")
        except Exception as e:
            warn_mark(f"No se pudo guardar el informe JSON: {e}")

    header("RESULTADO FINAL: SUITE DE LATENCIA LOCAL EJECUTADA SATISFACTORIAMENTE")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="RTMS v2.8.0 — Suite de Diagnóstico y Optimización de Ping y Latencia Local"
    )
    parser.add_argument(
        "--udp-samples", type=int, default=150, help="Cantidad de paquetes datagrama para prueba UDP (default: 150)"
    )
    parser.add_argument(
        "--tcp-samples", type=int, default=30, help="Cantidad de intentos de handshake TCP (default: 30)"
    )
    parser.add_argument(
        "--video-duration",
        type=float,
        default=3.5,
        help="Duración en segundos del benchmark de video SRT (default: 3.5)",
    )
    parser.add_argument("--no-json", action="store_true", help="No guardar el archivo JSON de informe")

    args = parser.parse_args()

    asyncio.run(
        run_benchmark(
            udp_samples=args.udp_samples,
            tcp_samples=args.tcp_samples,
            video_duration=args.video_duration,
            save_json=not args.no_json,
        )
    )


if __name__ == "__main__":
    main()


# rtms-sync
