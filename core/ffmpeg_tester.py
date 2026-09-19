# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de rendimiento y diagnóstico para flujos FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Diagnóstico, pruebas de rendimiento y análisis de latencia para flujos FFmpeg."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.hardware import _WIN_FLAGS, get_ffmpeg_bin, has_ffmpeg_binary

logger = logging.getLogger("rtms.ffmpeg_tester")


@dataclass
class StreamDigestResult:
    """Resultado estructurado de la digestión y análisis de un flujo de video recibido."""

    protocol: str
    url: str
    is_connected: bool = False
    connection_time_ms: float = 0.0
    width: int = 0
    height: int = 0
    detected_fps: float = 0.0
    codec: str = ""
    pixel_format: str = ""
    frames_decoded: int = 0
    dropped_frames: int = 0
    duplicate_frames: int = 0
    elapsed_seconds: float = 0.0
    real_fps: float = 0.0
    avg_bitrate_kbps: float = 0.0
    speed: str = ""
    errors: List[str] = field(default_factory=list)
    raw_stderr: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.is_connected and self.frames_decoded > 0 and len(self.errors) == 0

    def summary(self) -> str:
        status = "EXITOSA" if self.is_success else "FALLIDA"
        lines = [
            f"--- Digestión de Stream [{self.protocol.upper()}] : {status} ---",
            f"  URL: {self.url}",
            f"  Conexión entablada: {'SÍ' if self.is_connected else 'NO'} ({self.connection_time_ms:.1f} ms)",
            f"  Resolución: {self.width}x{self.height} | Códec: {self.codec} ({self.pixel_format})",
            f"  FPS Declarado: {self.detected_fps:.1f} | FPS Decodificado Real: {self.real_fps:.2f}",
            f"  Cuadros Decodificados: {self.frames_decoded} en {self.elapsed_seconds:.2f}s",
            f"  Cuadros Caídos: {self.dropped_frames} | Duplicados: {self.duplicate_frames}",
            f"  Velocidad: {self.speed} | Bitrate: {self.avg_bitrate_kbps:.1f} kbps",
        ]
        if self.errors:
            lines.append(f"  Errores detectados ({len(self.errors)}):")
            for err in self.errors[:5]:
                lines.append(f"    ! {err}")
        return "\n".join(lines)


class VideoReceiverDigest:
    """
    Cliente receptor ("digeridor") de video.
    Conecta al flujo mediante FFmpeg, analiza los descriptores de entrada, decodifica cuadros
    y mide en tiempo real FPS, estabilidad, caída de paquetes y errores de sintaxis H.264.
    """

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()

    async def digest_stream(
        self,
        url: str,
        protocol: str,
        duration_seconds: float = 4.0,
        timeout_seconds: float = 8.0,
        extra_input_args: Optional[List[str]] = None,
    ) -> StreamDigestResult:
        result = StreamDigestResult(protocol=protocol, url=url)
        if not has_ffmpeg_binary():
            result.errors.append("Binario FFmpeg no encontrado.")
            return result

        cmd = [self.ffmpeg_bin, "-hide_banner"]

        if extra_input_args:
            cmd.extend(extra_input_args)

        # Usar -progress pipe:1 para telemetría frame a frame determinista
        cmd.extend(["-i", url, "-t", str(duration_seconds), "-f", "null", "-", "-progress", "pipe:1"])

        start_time = time.time()
        conn_start = time.time()
        first_frame_time: Optional[float] = None
        last_frame_time: Optional[float] = None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=_WIN_FLAGS
            )
        except Exception as e:
            result.errors.append(f"No se pudo lanzar el receptor: {e}")
            return result

        stats_pattern = re.compile(
            r"Stream #0:0.*Video:\s*(\w+).*?,\s*([a-zA-Z0-9_]+).*?,\s*(\d+)x(\d+).*?,\s*([0-9.]+)\s*fps"
        )
        fatal_patterns = [
            "connection refused",
            "password required",
            "error:unsecure",
            "reject reported",
            "i/o error",
            "could not find video device",
        ]

        # Leer stdout (progreso) y stderr (logs y metadatos) asíncronamente
        async def read_stdout():
            nonlocal first_frame_time, last_frame_time
            last_frame = 0
            async for line in proc.stdout:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                parts = line_str.split("=", 1)
                if len(parts) == 2:
                    k, v = parts[0].strip(), parts[1].strip()
                    if k == "frame":
                        try:
                            last_frame = int(v)
                            now = time.time()
                            if last_frame > 0:
                                if not result.is_connected:
                                    result.is_connected = True
                                    result.connection_time_ms = (now - conn_start) * 1000.0
                                if first_frame_time is None:
                                    first_frame_time = now
                                last_frame_time = now
                            result.frames_decoded = last_frame
                        except ValueError:
                            pass
                    elif k == "drop_frames":
                        try:
                            result.dropped_frames = int(v)
                        except ValueError:
                            pass
                    elif k == "dup_frames":
                        try:
                            result.duplicate_frames = int(v)
                        except ValueError:
                            pass
                    elif k == "speed":
                        result.speed = v
                    elif k == "bitrate":
                        m = re.search(r"([0-9.]+)kbits/s", v)
                        if m:
                            try:
                                result.avg_bitrate_kbps = float(m.group(1))
                            except ValueError:
                                pass

        async def read_stderr():
            async for line in proc.stderr:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                result.raw_stderr.append(line_str)

                # Detección de metadatos de video
                m = stats_pattern.search(line_str)
                if m:
                    result.codec = m.group(1)
                    result.pixel_format = m.group(2)
                    result.width = int(m.group(3))
                    result.height = int(m.group(4))
                    try:
                        result.detected_fps = float(m.group(5))
                    except ValueError:
                        pass
                    if not result.is_connected:
                        result.is_connected = True
                        result.connection_time_ms = (time.time() - conn_start) * 1000.0

                # Detección de errores fatales
                lower = line_str.lower()
                for pat in fatal_patterns:
                    if pat in lower and not any(pat in e.lower() for e in result.errors):
                        result.errors.append(line_str)

        try:
            await asyncio.wait_for(asyncio.gather(read_stdout(), read_stderr(), proc.wait()), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            result.errors.append(f"Timeout esperando respuesta del flujo tras {timeout_seconds}s")
            try:
                proc.terminate()
                await asyncio.sleep(0.2)
                proc.kill()
            except Exception:
                pass

        elapsed_total = time.time() - start_time
        result.elapsed_seconds = elapsed_total
        if first_frame_time and last_frame_time and last_frame_time > first_frame_time:
            stream_duration = last_frame_time - first_frame_time
            result.real_fps = result.frames_decoded / stream_duration
        elif result.detected_fps > 0 and result.frames_decoded > 0:
            # Aproximación basada en duración de frames decodificados
            result.real_fps = result.detected_fps
        elif elapsed_total > 0:
            result.real_fps = result.frames_decoded / elapsed_total

        return result


class VirtualCameraSource:
    """
    Generador de cámara virtual sintética mediante FFmpeg lavfi.
    Produce video en tiempo real (-re) con reloj en pantalla, resolución y framerate exactos,
    sirviendo como generador de referencia calibrado.
    """

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
        self.process: Optional[asyncio.subprocess.Process] = None
        self._log_task: Optional[asyncio.Task] = None
        self.logs: List[str] = []

    def build_command(
        self,
        output_url: str,
        resolution: str = "1080p",
        fps: int = 60,
        encoder: str = "libx264",
        bitrate: int = 6000,
        zerolatency: bool = True,
        repeat_headers: bool = True,
        pattern: str = "testsrc2",
    ) -> List[str]:
        res_map = {"480p": "854x480", "720p": "1280x720", "1080p": "1920x1080", "1440p": "2560x1440", "4K": "3840x2160"}
        res_str = res_map.get(resolution, resolution)
        gop = fps  # 1 keyframe por segundo para ultra-baja latencia y enganche inmediato

        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-re",  # Ritmo de reloj en tiempo real
            "-f",
            "lavfi",
            "-i",
            f"{pattern}=size={res_str}:rate={fps}",
            "-pix_fmt",
            "yuv420p",
        ]

        # Configuración del codificador
        if encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "ultrafast"]
            if zerolatency:
                cmd += ["-tune", "zerolatency"]
            if repeat_headers:
                cmd += ["-x264-params", "repeat-headers=1"]
        elif encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", "p1"]
            if zerolatency:
                cmd += ["-tune", "ull", "-delay", "0", "-zerolatency", "1"]
            if repeat_headers:
                cmd += ["-forced-idr", "1"]
        elif encoder == "h264_qsv":
            cmd += ["-c:v", "h264_qsv", "-preset", "veryfast"]
        elif encoder == "h264_amf":
            cmd += ["-c:v", "h264_amf", "-quality", "speed", "-usage", "ultralowlatency"]
        else:
            cmd += ["-c:v", encoder]

        # Bitrate y GOP
        bk = f"{bitrate}k"
        maxbk = f"{int(bitrate * 1.15)}k"
        bufk = f"{bitrate * 2}k"
        cmd += ["-b:v", bk, "-maxrate", maxbk, "-bufsize", bufk, "-g", str(gop), "-an"]

        # Formato de multiplexación MPEG-TS optimizado
        if zerolatency:
            cmd += ["-f", "mpegts", "-muxdelay", "0", "-muxpreload", "0", "-flush_packets", "1"]
        else:
            cmd += ["-f", "mpegts"]

        cmd.append(output_url)
        return cmd

    async def start(
        self,
        output_url: str,
        resolution: str = "1080p",
        fps: int = 60,
        encoder: str = "libx264",
        bitrate: int = 6000,
        zerolatency: bool = True,
        repeat_headers: bool = True,
    ) -> bool:
        cmd = self.build_command(
            output_url=output_url,
            resolution=resolution,
            fps=fps,
            encoder=encoder,
            bitrate=bitrate,
            zerolatency=zerolatency,
            repeat_headers=repeat_headers,
        )
        self.logs.clear()

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                creationflags=_WIN_FLAGS,
            )
            self._log_task = asyncio.create_task(self._collect_logs())
            return True
        except Exception as e:
            logger.error(f"Error lanzando cámara virtual: {e}")
            return False

    async def _collect_logs(self):
        if not self.process:
            return
        try:
            async for line in self.process.stderr:
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str:
                    self.logs.append(line_str)
        except Exception:
            pass

    async def stop(self, timeout: float = 2.0):
        if not self.process:
            return
        try:
            if self.process.stdin:
                self.process.stdin.write(b"q\n")
                await self.process.stdin.drain()
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
        except Exception:
            try:
                self.process.terminate()
                await asyncio.sleep(0.2)
                self.process.kill()
            except Exception:
                pass
        self.process = None
        if self._log_task and not self._log_task.done():
            self._log_task.cancel()


class FFmpegDiagnosticSuite:
    """
    Suite integral de diagnóstico y validación en vivo para todas las funciones
    utilizadas de FFmpeg en RTMS.
    """

    def __init__(self):
        self.receiver = VideoReceiverDigest()
        self.virtual_cam = VirtualCameraSource()

    def check_binary_and_protocols(self) -> Dict[str, Any]:
        """Verifica la existencia física, versión y protocolos requeridos en el binario FFmpeg."""
        bin_path = get_ffmpeg_bin()
        available = has_ffmpeg_binary()
        report = {
            "available": available,
            "path": bin_path,
            "version": "N/A",
            "srt_enabled": False,
            "udp_enabled": False,
            "dshow_enabled": False,
            "nvenc_enabled": False,
            "amf_enabled": False,
            "qsv_enabled": False,
            "libx264_enabled": False,
        }
        if not available:
            return report

        import subprocess

        try:
            res = subprocess.run(
                [bin_path, "-version"], capture_output=True, text=True, timeout=5, creationflags=_WIN_FLAGS
            )
            if res.stdout:
                report["version"] = res.stdout.splitlines()[0]
        except Exception:
            pass

        try:
            res = subprocess.run(
                [bin_path, "-protocols"], capture_output=True, text=True, timeout=5, creationflags=_WIN_FLAGS
            )
            out = (res.stdout or "").lower()
            report["srt_enabled"] = "srt" in out
            report["udp_enabled"] = "udp" in out
        except Exception:
            pass

        try:
            res = subprocess.run(
                [bin_path, "-devices"], capture_output=True, text=True, timeout=5, creationflags=_WIN_FLAGS
            )
            report["dshow_enabled"] = "dshow" in (res.stdout or "").lower()
        except Exception:
            pass

        try:
            res = subprocess.run(
                [bin_path, "-encoders"], capture_output=True, text=True, timeout=5, creationflags=_WIN_FLAGS
            )
            out = (res.stdout or "").lower()
            report["nvenc_enabled"] = "h264_nvenc" in out
            report["amf_enabled"] = "h264_amf" in out
            report["qsv_enabled"] = "h264_qsv" in out
            report["libx264_enabled"] = "libx264" in out
        except Exception:
            pass

        return report

    def probe_dshow_camera_caps(self, friendly_name: str) -> Dict[str, Any]:
        """
        Sondea las capacidades reales (resoluciones, FPS y pixel formats) de una cámara física DirectShow
        ejecutando ffmpeg -list_options true -f dshow -i video="...".
        """
        bin_path = get_ffmpeg_bin()
        import subprocess

        caps = {
            "friendly_name": friendly_name,
            "supported_modes": [],
            "max_resolution": "Desconocida",
            "max_fps": 0,
            "supports_1080p60": False,
            "error": None,
        }
        try:
            res = subprocess.run(
                [bin_path, "-hide_banner", "-list_options", "true", "-f", "dshow", "-i", f"video={friendly_name}"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_WIN_FLAGS,
            )
            output = res.stderr or ""
            pattern = re.compile(
                r"pixel_format=([a-zA-Z0-9]+)\s+min s=(\d+)x(\d+)\s+fps=([0-9.]+)\s+max s=(\d+)x(\d+)\s+fps=([0-9.]+)"
            )
            max_w, max_h, max_fps = 0, 0, 0
            for line in output.splitlines():
                m = pattern.search(line)
                if m:
                    fmt = m.group(1)
                    w, h, fps = int(m.group(5)), int(m.group(6)), float(m.group(7))
                    caps["supported_modes"].append({"pixel_format": fmt, "width": w, "height": h, "fps": fps})
                    if (w * h) > (max_w * max_h) or (w * h == max_w * max_h and fps > max_fps):
                        max_w, max_h = w, h
                        max_fps = fps

            if max_w > 0:
                caps["max_resolution"] = f"{max_w}x{max_h}"
                caps["max_fps"] = max_fps
                caps["supports_1080p60"] = max_w >= 1920 and max_h >= 1080 and max_fps >= 59.0
        except Exception as e:
            caps["error"] = str(e)

        return caps

    async def benchmark_encoder(
        self, encoder: str, resolution: str = "1080p", fps: int = 60, frames: int = 180
    ) -> Dict[str, Any]:
        """
        Evalúa el rendimiento de codificación a 1080p@60fps sin cuellos de botella de red.
        Mide el FPS de codificación alcanzado y el tiempo invertido.
        """
        res_map = {"720p": "1280x720", "1080p": "1920x1080", "4K": "3840x2160"}
        res_str = res_map.get(resolution, resolution)
        ffmpeg_bin = get_ffmpeg_bin()

        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={res_str}:rate={fps}",
            "-pix_fmt",
            "yuv420p",
        ]

        if encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]
        elif encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ull", "-delay", "0", "-zerolatency", "1"]
        elif encoder == "h264_qsv":
            cmd += ["-c:v", "h264_qsv", "-preset", "veryfast"]
        elif encoder == "h264_amf":
            cmd += ["-c:v", "h264_amf", "-quality", "speed", "-usage", "ultralowlatency"]
        else:
            cmd += ["-c:v", encoder]

        cmd += ["-frames:v", str(frames), "-f", "null", "-"]

        t0 = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE, creationflags=_WIN_FLAGS
        )
        _, stderr = await proc.communicate()
        elapsed = time.time() - t0
        fps_achieved = frames / max(0.001, elapsed)

        return {
            "encoder": encoder,
            "resolution": resolution,
            "target_fps": fps,
            "frames_tested": frames,
            "elapsed_seconds": elapsed,
            "achieved_fps": fps_achieved,
            "success": (proc.returncode == 0),
            "can_maintain_realtime": fps_achieved >= (fps * 0.95),
        }

    async def test_srt_connection(
        self,
        port: int = 9981,
        resolution: str = "720p",
        fps: int = 30,
        passphrase_sender: str = "",
        passphrase_receiver: str = "",
        duration_seconds: float = 3.0,
    ) -> StreamDigestResult:
        """
        Prueba completa de entablado y transmisión SRT:
        Emisor (Listener) <---> Receptor (Caller)
        """
        sender_url = f"srt://0.0.0.0:{port}?mode=listener&latency=120000&transtype=live&smoother=live&tlpktdrop=1"
        if passphrase_sender:
            sender_url += f"&passphrase={passphrase_sender}"

        receiver_url = f"srt://127.0.0.1:{port}?mode=caller&latency=120000"
        if passphrase_receiver:
            receiver_url += f"&passphrase={passphrase_receiver}"

        cam = VirtualCameraSource()
        started = await cam.start(
            output_url=sender_url,
            resolution=resolution,
            fps=fps,
            encoder="libx264",
            bitrate=3000,
            zerolatency=True,
            repeat_headers=True,
        )
        if not started:
            res = StreamDigestResult(protocol="srt", url=receiver_url)
            res.errors.append("No se pudo iniciar el emisor SRT Listener.")
            return res

        await asyncio.sleep(0.4)

        try:
            digest = await self.receiver.digest_stream(
                url=receiver_url,
                protocol="srt",
                duration_seconds=duration_seconds,
                timeout_seconds=duration_seconds + 5.0,
                extra_input_args=["-probesize", "128000", "-analyzeduration", "500000"],
            )
        finally:
            await cam.stop()

        return digest

    async def test_udp_connection(
        self,
        port: int = 9982,
        multicast: bool = True,
        resolution: str = "1080p",
        fps: int = 60,
        buffer_size: int = 4194304,
        repeat_headers: bool = True,
        duration_seconds: float = 3.0,
    ) -> StreamDigestResult:
        """
        Prueba completa de entablado y transmisión UDP (Multicast o Unicast).
        """
        if multicast:
            ip_last = (port % 200) + 1
            ip_addr = f"239.255.0.{ip_last}"
        else:
            ip_addr = "127.0.0.1"

        sender_url = f"udp://{ip_addr}:{port}?pkt_size=1316&buffer_size={buffer_size}"
        receiver_url = f"udp://{ip_addr}:{port}?overrun_nonfatal=1&fifo_size=50000000&buffer_size={buffer_size}"

        cam = VirtualCameraSource()
        started = await cam.start(
            output_url=sender_url,
            resolution=resolution,
            fps=fps,
            encoder="libx264",
            bitrate=6000,
            zerolatency=True,
            repeat_headers=repeat_headers,
        )
        if not started:
            res = StreamDigestResult(protocol="udp", url=receiver_url)
            res.errors.append("No se pudo iniciar el emisor UDP.")
            return res

        await asyncio.sleep(0.5)

        try:
            digest = await self.receiver.digest_stream(
                url=receiver_url,
                protocol="udp",
                duration_seconds=duration_seconds,
                timeout_seconds=duration_seconds + 5.0,
                extra_input_args=["-probesize", "128000", "-analyzeduration", "500000"],
            )
        finally:
            await cam.stop()

        return digest
