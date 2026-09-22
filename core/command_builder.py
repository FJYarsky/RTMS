# ==============================================================================
# RTMS — Real-Time Multicam System
# Construcción y optimización de comandos para transmisión con FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Construcción de argumentos de línea de comandos para procesos FFmpeg."""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.hardware import get_ffmpeg_bin, hardware_detector
from core.sanitizer import sanitize_url
from core.stream_proc import StreamProc, build_stream_url

logger = logging.getLogger("rtms.command_builder")

RESOLUTION_MAP: Dict[str, str] = {
    "480p": "854x480",
    "720p": "1280x720",
    "1080p": "1920x1080",
    "1440p": "2560x1440",
    "4K": "3840x2160",
}


async def build_ffmpeg_command(
    cfg: Dict[str, Any],
    force_cpu: bool = False,
    proc: Optional[StreamProc] = None,
    best_encoder_getter: Optional[Callable[[], Any]] = None,
) -> Tuple[List[str], str, str]:
    """
    Construye la lista de argumentos para FFmpeg, la URL sanitizada y el encoder a utilizar.
    Soporta generador virtual lavfi (virtual://, testsrc2) y aceleración por hardware (NVENC, QSV, AMF, CPU).
    """
    video_size = RESOLUTION_MAP.get(cfg.get("resolution", "720p"), "1280x720")
    fps = cfg.get("fps", 30)
    zerolatency = cfg.get("zerolatency", True)
    # En modo zerolatency el GOP es de 1 segundo para enganche IDR ultrarrápido en decodificadores
    gop = fps if zerolatency else (fps * 2)
    bitrate = cfg.get("bitrate", 3000)

    bk = f"{bitrate}k"
    maxbk = f"{int(bitrate * 1.15)}k"
    bufk = f"{bitrate * 2}k"

    ffmpeg_bin = get_ffmpeg_bin()
    raw_device = cfg.get("device_path", cfg.get("friendly_name", ""))
    is_virtual = (
        raw_device.startswith("virtual://")
        or raw_device.startswith("testsrc")
        or cfg.get("is_virtual_generator", False)
    )

    cmd = [ffmpeg_bin, "-hide_banner", "-stats", "-stats_period", "1"]

    if is_virtual:
        cmd += ["-re", "-f", "lavfi", "-i", f"testsrc2=size={video_size}:rate={fps}"]
    else:
        escaped_device = raw_device.replace(":", "\\:")
        cmd += [
            "-f",
            "dshow",
            "-rtbufsize",
            "150M",
            "-video_size",
            video_size,
            "-framerate",
            str(fps),
            "-i",
            f"video={escaped_device}",
        ]

    cmd += ["-pix_fmt", "yuv420p"]

    if force_cpu:
        encoder = "libx264"
    else:
        encoder = cfg.get("encoder", "auto")
        if encoder == "auto":
            if proc and proc.per_stream_encoder:
                encoder = proc.per_stream_encoder
            elif best_encoder_getter:
                encoder = await best_encoder_getter()
            else:
                encoder = await hardware_detector.get_best_encoder()
            if proc:
                proc.per_stream_encoder = encoder

    # Ajuste de flags del codificador según opción zerolatency
    if zerolatency:
        if encoder == "libx264":
            cmd += [
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-x264-params",
                "repeat-headers=1",
            ]
        elif encoder == "h264_nvenc":
            cmd += [
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p1",
                "-tune",
                "ull",
                "-delay",
                "0",
                "-zerolatency",
                "1",
                "-forced-idr",
                "1",
            ]
        elif encoder == "h264_amf":
            cmd += ["-c:v", "h264_amf", "-quality", "speed", "-usage", "ultralowlatency"]
        elif encoder == "h264_qsv":
            cmd += ["-c:v", "h264_qsv", "-preset", "veryfast"]
        else:
            cmd += ["-c:v", encoder]
    else:
        # Perfil equilibrado de broadcast (sin comprometer calidad innecesariamente)
        if encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-x264-params", "repeat-headers=1"]
        elif encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-forced-idr", "1"]
        elif encoder == "h264_amf":
            cmd += ["-c:v", "h264_amf", "-quality", "balanced"]
        elif encoder == "h264_qsv":
            cmd += ["-c:v", "h264_qsv", "-preset", "medium"]
        else:
            cmd += ["-c:v", encoder]

    cmd += ["-b:v", bk, "-maxrate", maxbk, "-bufsize", bufk, "-g", str(gop), "-an"]

    protocol = cfg.get("protocol", "srt")
    port = cfg.get("port", 9000)
    passphrase = cfg.get("srt_passphrase", "")
    latency_ms = int(cfg.get("srt_latency", 120))
    cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{port}"
    clean_cam_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(cam_id))

    if protocol == "srt":
        from core.mediamtx_mgr import mediamtx_manager

        mediamtx_port = mediamtx_manager.get_srt_port()
        # En arquitectura desacoplada con MediaMTX (Fase 2), FFmpeg publica localmente
        # por loopback (127.0.0.1) sin frase de paso para evitar rechazo BADSECRET.
        # La protección de contraseña se aplica a los lectores externos (OBS/vMix)
        # mediante srtReadPassphrase en MediaMTX.
        raw_url = build_stream_url(
            protocol="srt",
            port=mediamtx_port,
            passphrase="",
            mode="caller",
            latency_ms=latency_ms,
            zerolatency=zerolatency,
            streamid=f"publish:{clean_cam_id}",
        )
    else:
        udp_mode = cfg.get("udp_mode", "multicast")
        udp_host = cfg.get("udp_host", "127.0.0.1")
        raw_url = build_stream_url(
            protocol=protocol,
            port=port,
            passphrase=passphrase,
            mode="listener",
            latency_ms=latency_ms,
            zerolatency=zerolatency,
            udp_mode=udp_mode,
            udp_host=udp_host,
        )

    if zerolatency:
        cmd += [
            "-bsf:v",
            "dump_extra",
            "-f",
            "mpegts",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-pat_period",
            "0.1",
            "-pcr_period",
            "20",
            "-flush_packets",
            "1",
            raw_url,
        ]
    else:
        cmd += ["-bsf:v", "dump_extra", "-f", "mpegts", raw_url]

    sanitized_url = sanitize_url(raw_url)
    return cmd, sanitized_url, encoder


# Alias canónico
build_command = build_ffmpeg_command
