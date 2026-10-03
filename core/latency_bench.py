# ==============================================================================
# RTMS — Real-Time Multicam System
# Diagnóstico, medición de ping y minimización de latencia en bucle local (Loopback).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Módulo de diagnóstico y evaluación de latencia y ping local.
Mide el tiempo de ida y vuelta (RTT / Ping) a nivel de socket, el retraso de entrega
de tramas de video (Pipeline Latency), la variación de retardo (Jitter) y determina
la configuración óptima de caché para el reproductor VLC en la misma máquina.
"""

import asyncio
import logging
import math
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.hardware import get_ffmpeg_bin

logger = logging.getLogger("rtms.latency_bench")

VLC_PATH = r"C:\Program Files\VideoLAN\VLC\vlc.exe"


def calculate_percentile(data: List[float], p: float) -> float:
    """Calcula el percentil p (0.0 a 1.0) usando el método de rango más cercano."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(math.ceil(p * len(sorted_data))) - 1
    return sorted_data[max(0, min(idx, len(sorted_data) - 1))]


@dataclass
class PingStatistics:
    """Estadísticas detalladas de latencia y ping."""

    protocol: str
    target: str
    samples_count: int
    min_ms: float
    avg_ms: float
    max_ms: float
    jitter_ms: float
    loss_rate: float
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"[{self.protocol.upper()} a {self.target}] Ping Min: {self.min_ms:.2f}ms | "
            f"Avg: {self.avg_ms:.2f}ms | Max: {self.max_ms:.2f}ms | "
            f"p95: {self.p95_ms:.2f}ms | p99: {self.p99_ms:.2f}ms | "
            f"Jitter: {self.jitter_ms:.2f}ms | Pérdida: {self.loss_rate * 100:.1f}%"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "target": self.target,
            "samples_count": self.samples_count,
            "min_ms": round(self.min_ms, 4),
            "avg_ms": round(self.avg_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "jitter_ms": round(self.jitter_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "loss_rate": round(self.loss_rate, 4),
            "details": self.details,
        }


@dataclass
class VideoPipelineLatencyReport:
    """Informe de latencia de transporte de video y primer cuadro (TTFF)."""

    protocol: str
    url: str
    time_to_first_frame_ms: float
    fps_measured: float
    frames_received: int
    inter_frame_jitter_ms: float
    buffer_underruns: int
    recommended_vlc_caching_ms: int
    status: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "url": self.url,
            "time_to_first_frame_ms": round(self.time_to_first_frame_ms, 2),
            "fps_measured": round(self.fps_measured, 2),
            "frames_received": self.frames_received,
            "inter_frame_jitter_ms": round(self.inter_frame_jitter_ms, 2),
            "buffer_underruns": self.buffer_underruns,
            "recommended_vlc_caching_ms": self.recommended_vlc_caching_ms,
            "status": self.status,
            "notes": self.notes,
        }


class LatencyBenchmarkEngine:
    """
    Motor y herramienta de diagnóstico de latencia para optimizar el ping en la misma PC.
    """

    def __init__(self, ffmpeg_bin: Optional[str] = None, vlc_path: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
        self.vlc_path = vlc_path if vlc_path is not None else (VLC_PATH if os.path.exists(VLC_PATH) else None)

    @classmethod
    def measure_udp_socket_ping(
        cls,
        port: int = 9876,
        iterations: int = 50,
        host: str = "127.0.0.1",
        timeout: float = 0.05,
        bind_receiver: bool = True,
    ) -> PingStatistics:
        """
        Mide el ping (RTT) a nivel de socket UDP en loopback local (127.0.0.1).
        Envía paquetes datagrama con marcas de tiempo en nanosegundos y mide el tiempo de tránsito.
        """
        if iterations <= 0:
            return PingStatistics(
                protocol="udp_loopback",
                target=f"{host}:{port}",
                samples_count=0,
                min_ms=0.0,
                avg_ms=0.0,
                max_ms=0.0,
                jitter_ms=0.0,
                loss_rate=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
            )

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver = None

        if bind_receiver:
            try:
                receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                receiver.bind((host, port))
                receiver.setblocking(False)
            except OSError as e:
                logger.debug(f"Could not bind receiver socket on {host}:{port}: {e}. Falling back to echo mode.")
                if receiver:
                    receiver.close()
                receiver = None

        rtts_ms: List[float] = []
        lost = 0

        for _ in range(iterations):
            t_send = time.perf_counter_ns()
            try:
                sender.sendto(b"RTMS_PING_" + str(t_send).encode("ascii"), (host, port))
            except OSError:
                lost += 1
                time.sleep(0.001)
                continue

            received = False
            t_start = time.perf_counter()

            if receiver is not None:
                while (time.perf_counter() - t_start) < timeout:
                    try:
                        data, _ = receiver.recvfrom(256)
                        t_recv = time.perf_counter_ns()
                        if data.startswith(b"RTMS_PING_"):
                            rtt_ms = (t_recv - t_send) / 1_000_000.0
                            rtts_ms.append(rtt_ms)
                            received = True
                            break
                    except BlockingIOError:
                        time.sleep(0.0001)
                    except OSError:
                        break
            else:
                sender.settimeout(timeout)
                try:
                    data, _ = sender.recvfrom(256)
                    t_recv = time.perf_counter_ns()
                    if data.startswith(b"RTMS_PING_"):
                        rtt_ms = (t_recv - t_send) / 1_000_000.0
                        rtts_ms.append(rtt_ms)
                        received = True
                except (socket.timeout, BlockingIOError, OSError):
                    pass

            if not received:
                lost += 1
            time.sleep(0.001)

        sender.close()
        if receiver is not None:
            receiver.close()

        if not rtts_ms:
            return PingStatistics(
                protocol="udp_loopback",
                target=f"{host}:{port}",
                samples_count=0,
                min_ms=0.0,
                avg_ms=0.0,
                max_ms=0.0,
                jitter_ms=0.0,
                loss_rate=1.0,
                p95_ms=0.0,
                p99_ms=0.0,
            )

        min_val = min(rtts_ms)
        max_val = max(rtts_ms)
        avg_val = sum(rtts_ms) / len(rtts_ms)
        variance = sum((x - avg_val) ** 2 for x in rtts_ms) / len(rtts_ms)
        jitter_val = math.sqrt(variance)
        loss_rate = lost / iterations
        p95_val = calculate_percentile(rtts_ms, 0.95)
        p99_val = calculate_percentile(rtts_ms, 0.99)

        return PingStatistics(
            protocol="udp_loopback",
            target=f"{host}:{port}",
            samples_count=len(rtts_ms),
            min_ms=min_val,
            avg_ms=avg_val,
            max_ms=max_val,
            jitter_ms=jitter_val,
            loss_rate=loss_rate,
            p95_ms=p95_val,
            p99_ms=p99_val,
        )

    @classmethod
    def measure_tcp_connect_ping(
        cls,
        port: int = 9997,
        host: str = "127.0.0.1",
        iterations: int = 20,
        timeout: float = 0.5,
    ) -> PingStatistics:
        """
        Mide el tiempo de establecimiento de conexión TCP (TCP SYN/ACK Round-Trip Ping).
        Ideal para medir el ping de comunicación con la API de MediaMTX.
        """
        if iterations <= 0:
            return PingStatistics(
                protocol="tcp_handshake",
                target=f"{host}:{port}",
                samples_count=0,
                min_ms=0.0,
                avg_ms=0.0,
                max_ms=0.0,
                jitter_ms=0.0,
                loss_rate=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
            )

        rtts_ms: List[float] = []
        lost = 0

        for _ in range(iterations):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            t_start = time.perf_counter_ns()
            try:
                s.connect((host, port))
                t_end = time.perf_counter_ns()
                rtts_ms.append((t_end - t_start) / 1_000_000.0)
            except Exception:
                lost += 1
            finally:
                s.close()
            time.sleep(0.002)

        if not rtts_ms:
            return PingStatistics(
                protocol="tcp_handshake",
                target=f"{host}:{port}",
                samples_count=0,
                min_ms=0.0,
                avg_ms=0.0,
                max_ms=0.0,
                jitter_ms=0.0,
                loss_rate=1.0,
                p95_ms=0.0,
                p99_ms=0.0,
            )

        min_val = min(rtts_ms)
        max_val = max(rtts_ms)
        avg_val = sum(rtts_ms) / len(rtts_ms)
        variance = sum((x - avg_val) ** 2 for x in rtts_ms) / len(rtts_ms)
        jitter_val = math.sqrt(variance)
        loss_rate = lost / iterations
        p95_val = calculate_percentile(rtts_ms, 0.95)
        p99_val = calculate_percentile(rtts_ms, 0.99)

        return PingStatistics(
            protocol="tcp_handshake",
            target=f"{host}:{port}",
            samples_count=len(rtts_ms),
            min_ms=min_val,
            avg_ms=avg_val,
            max_ms=max_val,
            jitter_ms=jitter_val,
            loss_rate=loss_rate,
            p95_ms=p95_val,
            p99_ms=p99_val,
        )

    async def benchmark_video_pipeline(
        self,
        protocol: str = "udp",
        port: int = 9028,
        stream_name: str = "ping_bench_cam",
        srt_latency_ms: int = 20,
        duration_sec: float = 3.0,
    ) -> VideoPipelineLatencyReport:
        """
        Transmite video sintético a 60 FPS con GOP de 15 frames y mide el tiempo
        hasta la entrega del primer cuadro decodificable (TTFF) y la fluctuación entre cuadros.
        """
        is_srt = protocol.lower() == "srt"
        if is_srt:
            ingest_url = (
                f"srt://127.0.0.1:{port}?streamid=publish:{stream_name}"
                f"&latency={srt_latency_ms * 1000}&tlpktdrop=1&rcvbuf=65536&sndbuf=65536"
            )
            read_url = f"srt://127.0.0.1:{port}?streamid=read:{stream_name}&latency={srt_latency_ms * 1000}"
        else:
            ingest_url = f"udp://127.0.0.1:{port}?pkt_size=1316&buffer_size=65536&overrun_nonfatal=1&fifo_size=5000"
            read_url = f"udp://127.0.0.1:{port}"

        # 1. Iniciar emisor FFmpeg prioritario con configuración de baja latencia
        sender_cmd = [
            self.ffmpeg_bin,
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
            "-threads",
            "4",
            "-slices",
            "4",
            "-bf",
            "0",
            "-bufsize",
            "62k",
            "-g",
            "15",
            "-fflags",
            "nobuffer+flush_packets",
            "-flags",
            "+low_delay",
            "-f",
            "mpegts",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-flush_packets",
            "1",
            "-pes_payload_size",
            "0",
            ingest_url,
        ]

        # 2. Configurar receptor para capturar marcas de tiempo de decodificación
        receiver_cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-fflags",
            "nobuffer+discardcorrupt",
            "-flags",
            "+low_delay",
            "-probesize",
            "32768",
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

        sender_proc = None
        receiver_proc = None
        t_client_start = time.perf_counter()

        if not is_srt:
            # En UDP loopback sin broker, el receptor debe enlazar el socket primero
            # para evitar que Windows responda con ICMP Port Unreachable al emisor.
            t_client_start = time.perf_counter()
            try:
                receiver_proc = await asyncio.create_subprocess_exec(
                    *receiver_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as e:
                logger.error(f"Failed to start FFmpeg receiver: {e}")
                return VideoPipelineLatencyReport(
                    protocol=protocol,
                    url=read_url,
                    time_to_first_frame_ms=0.0,
                    fps_measured=0.0,
                    frames_received=0,
                    inter_frame_jitter_ms=0.0,
                    buffer_underruns=1,
                    recommended_vlc_caching_ms=150,
                    status="FAILED",
                    notes=[f"FFmpeg receiver failed to launch: {e}"],
                )

            await asyncio.sleep(0.2)
            t_client_start = time.perf_counter()
            try:
                sender_proc = subprocess.Popen(sender_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                logger.error(f"Failed to start FFmpeg sender: {e}")
                if receiver_proc:
                    receiver_proc.terminate()
                    await receiver_proc.wait()
                return VideoPipelineLatencyReport(
                    protocol=protocol,
                    url=read_url,
                    time_to_first_frame_ms=0.0,
                    fps_measured=0.0,
                    frames_received=0,
                    inter_frame_jitter_ms=0.0,
                    buffer_underruns=1,
                    recommended_vlc_caching_ms=150,
                    status="FAILED",
                    notes=[f"FFmpeg sender failed to launch: {e}"],
                )
        else:
            # En SRT con MediaMTX broker, el emisor publica primero
            try:
                sender_proc = subprocess.Popen(sender_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                logger.error(f"Failed to start FFmpeg sender: {e}")
                return VideoPipelineLatencyReport(
                    protocol=protocol,
                    url=read_url,
                    time_to_first_frame_ms=0.0,
                    fps_measured=0.0,
                    frames_received=0,
                    inter_frame_jitter_ms=0.0,
                    buffer_underruns=1,
                    recommended_vlc_caching_ms=150,
                    status="FAILED",
                    notes=[f"FFmpeg sender failed to launch: {e}"],
                )

            await asyncio.sleep(0.8)

            t_client_start = time.perf_counter()
            try:
                receiver_proc = await asyncio.create_subprocess_exec(
                    *receiver_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as e:
                logger.error(f"Failed to start FFmpeg receiver: {e}")
                if sender_proc:
                    sender_proc.terminate()
                    sender_proc.wait(timeout=1.5)
                return VideoPipelineLatencyReport(
                    protocol=protocol,
                    url=read_url,
                    time_to_first_frame_ms=0.0,
                    fps_measured=0.0,
                    frames_received=0,
                    inter_frame_jitter_ms=0.0,
                    buffer_underruns=1,
                    recommended_vlc_caching_ms=150,
                    status="FAILED",
                    notes=[f"FFmpeg receiver failed to launch: {e}"],
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
            await asyncio.wait_for(asyncio.sleep(duration_sec), timeout=duration_sec + 1.0)
        finally:
            read_task.cancel()
            if receiver_proc:
                try:
                    receiver_proc.terminate()
                    await asyncio.wait_for(receiver_proc.wait(), timeout=1.0)
                except (ProcessLookupError, OSError):
                    pass
                except Exception:
                    try:
                        receiver_proc.kill()
                    except (ProcessLookupError, OSError):
                        pass

            if sender_proc:
                try:
                    sender_proc.terminate()
                    sender_proc.wait(timeout=1.5)
                except (ProcessLookupError, OSError):
                    pass
                except Exception:
                    try:
                        sender_proc.kill()
                    except (ProcessLookupError, OSError):
                        pass

        # Calcular métricas
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
            expected_interval = 1000.0 / 60.0  # 16.67 ms a 60 fps
            jitter_vals = [abs(iv - expected_interval) for iv in intervals]
            if jitter_vals:
                inter_frame_jitter_ms = sum(jitter_vals) / len(jitter_vals)

        # Determinar recomendación de caching para VLC en la misma PC
        # Si el jitter es muy bajo (< 5ms) y TTFF < 150ms, VLC puede operar a 30-50ms caching
        recommended_caching = 50 if inter_frame_jitter_ms < 6.0 else 100
        if inter_frame_jitter_ms < 3.0 and 0.0 < first_frame_ms < 100.0:
            recommended_caching = 30

        status = "OPTIMAL" if total_frames > 20 and first_frame_ms < 250.0 else "SUBOPTIMAL"
        if total_frames == 0:
            status = "NO_FRAMES"

        return VideoPipelineLatencyReport(
            protocol=protocol,
            url=read_url,
            time_to_first_frame_ms=first_frame_ms,
            fps_measured=measured_fps,
            frames_received=total_frames,
            inter_frame_jitter_ms=inter_frame_jitter_ms,
            buffer_underruns=0 if total_frames > 0 else 1,
            recommended_vlc_caching_ms=recommended_caching,
            status=status,
            notes=[
                f"TTFF: {first_frame_ms:.1f}ms",
                f"FPS medido: {measured_fps:.1f}",
                f"Jitter inter-frame: {inter_frame_jitter_ms:.2f}ms",
            ],
        )

    def test_vlc_caching_limits(
        self, url: str, caching_values: Optional[List[int]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Prueba diferentes niveles de buffering en VLC (:network-caching=X) en la misma PC
        para encontrar el límite inferior absoluto donde no se producen pérdidas de cuadros.
        """
        if caching_values is None:
            caching_values = [20, 50, 100, 150]
        if not self.vlc_path:
            return {}

        results = {}
        for cache_ms in caching_values:
            cmd = [
                self.vlc_path,
                "-I",
                "dummy",
                "-vvv",
                url,
                f":network-caching={cache_ms}",
                "vlc://quit",
                "--run-time=2",
            ]
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
                try:
                    _, err = p.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    _, err = p.communicate()
            except OSError as e:
                results[cache_ms] = {
                    "cache_ms": cache_ms,
                    "stable": False,
                    "underruns": 0,
                    "buffer_underruns": 0,
                    "picture_late_warnings": 0,
                    "jitter_warnings": 0,
                    "decoded": False,
                    "received_data": False,
                    "error": str(e),
                }
                continue

            err_lower = err.lower()
            picture_late = err_lower.count("picture is too late")
            buffer_underruns = err_lower.count("buffer underrun")
            jitter_warnings = err_lower.count("jitter") + picture_late
            underruns = buffer_underruns + picture_late
            decoded_any = any(k in err_lower for k in ["h264", "hevc", "ts demux", "avcodec"])
            received_data = "received first data" in err_lower or "pts" in err_lower

            results[cache_ms] = {
                "cache_ms": cache_ms,
                "stable": underruns == 0 and decoded_any,
                "underruns": underruns,
                "buffer_underruns": buffer_underruns,
                "picture_late_warnings": picture_late,
                "jitter_warnings": jitter_warnings,
                "decoded": decoded_any,
                "received_data": received_data,
            }

        return results


# Compatibilidad y alias
LocalLatencyBenchmark = LatencyBenchmarkEngine
