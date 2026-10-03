# ==============================================================================
# RTMS — Real-Time Multicam System
# Construcción y optimización de comandos para transmisión con FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Construcción de argumentos de línea de comandos para procesos FFmpeg."""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.config_mgr import is_virtual_device
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
    Soporta generador virtual lavfi (virtual://, testsrc2), aceleración por hardware (NVENC, QSV, AMF, CPU)
    y telemetría determinista estructurada vía stdout (-progress pipe:1).
    """
    video_size = RESOLUTION_MAP.get(cfg.get("resolution", "720p"), "1280x720")
    fps = cfg.get("fps", 30)
    zerolatency = cfg.get("zerolatency", True)
    # En modo zerolatency el GOP se calibra a 15 cuadros (500 ms a 30 fps) para enganche IDR de baja latencia sin saturar el decodificador
    if "gop" in cfg and cfg["gop"] is not None:
        try:
            gop = int(cfg["gop"])
        except (ValueError, TypeError):
            gop = max(15, int(fps * 0.5)) if zerolatency else (fps * 2)
    else:
        gop = max(15, int(fps * 0.5)) if zerolatency else (fps * 2)
    raw_bitrate = cfg.get("bitrate", 3000)
    try:
        if isinstance(raw_bitrate, str):
            clean_br = raw_bitrate.lower().rstrip("k").strip()
            bitrate = int(float(clean_br)) if clean_br else 3000
        elif raw_bitrate is None:
            bitrate = 3000
        else:
            bitrate = int(raw_bitrate)
    except (ValueError, TypeError):
        bitrate = 3000

    bk = f"{bitrate}k"
    maxbk = f"{bitrate}k" if zerolatency else f"{int(bitrate * 1.15)}k"
    if zerolatency:
        # VBV restringido a 1.5 frames (v2.8.2): fuerza bitrate plano, elimina packet bursting
        # Ejemplo: 3000kbps / 60fps * 1.5 = 75k; 3000kbps / 30fps * 1.5 = 150k
        vbv_bufsize_val = max(50, int(bitrate / max(1, fps) * 1.5))
        bufk = f"{vbv_bufsize_val}k"
    else:
        bufk = f"{bitrate}k"

    ffmpeg_bin = get_ffmpeg_bin()
    raw_device = cfg.get("device_path", cfg.get("friendly_name", ""))
    if not isinstance(raw_device, str):
        raw_device = str(raw_device or "")
    # Neutralizar bytes nulos y caracteres de control C0 para evitar caídas de subproceso (ValueError: embedded null byte)
    raw_device = raw_device.replace("\x00", "")
    raw_device = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_device).strip()

    is_virtual = (
        raw_device.startswith("virtual://")
        or raw_device.startswith("testsrc")
        or cfg.get("is_virtual_generator", False)
        or is_virtual_device(raw_device)
    )

    # Telemetría determinista a través de stdout (-progress pipe:1) suprimiendo stats en stderr
    cmd = [ffmpeg_bin, "-hide_banner", "-progress", "pipe:1", "-nostats"]
    if zerolatency:
        cmd += [
            "-fflags",
            "nobuffer+discardcorrupt",
            "-flags",
            "low_delay",
            "-avioflags",
            "direct",
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
        ]

    if is_virtual:
        cmd += ["-re", "-f", "lavfi", "-i", f"testsrc2=size={video_size}:rate={fps}"]
    else:
        dev_name = raw_device
        if dev_name.startswith("video="):
            dev_name = dev_name[6:]
        escaped_device = dev_name.replace(":", "\\:")
        dshow_args = ["-f", "dshow"]
        # Optimización de Silicio USB (v2.6.0):
        # Si el dispositivo no es virtual, verificar si el sensor DirectShow soporta compresión MJPEG.
        # Si use_mjpeg_input está configurado explícitamente se respeta; de lo contrario se sondea dinámicamente.
        is_1080p_or_more = any(res_key in video_size for res_key in ("1920x1080", "2560x1440", "3840x2160"))
        explicit_mjpeg = cfg.get("use_mjpeg_input")
        if explicit_mjpeg is not None:
            use_mjpeg = bool(explicit_mjpeg)
        elif proc and proc.mjpeg_supported is not None:
            use_mjpeg = bool(proc.mjpeg_supported)
        else:
            try:
                from core.hardware import probe_device_mjpeg_support

                use_mjpeg = await probe_device_mjpeg_support(raw_device)
                if proc:
                    proc.mjpeg_supported = use_mjpeg
            except Exception:
                use_mjpeg = is_1080p_or_more

            # v2.8.3: En 1080p+, priorizar el pin MJPEG para evitar que el bus USB 2.0
            # rechace NV12 sin comprimir y caiga al modo por defecto en 640x480 (4:3)
            if is_1080p_or_more and not getattr(proc, "mjpeg_input_failed", False):
                use_mjpeg = True

        if proc and getattr(proc, "mjpeg_input_failed", False):
            use_mjpeg = False

        dshow_options_failed = (proc and getattr(proc, "dshow_options_failed", False)) or cfg.get(
            "dshow_options_failed", False
        )

        if use_mjpeg:
            dshow_args += ["-vcodec", "mjpeg", "-rtbufsize", "3M"]
        else:
            # rtbufsize anti-bufferbloat (~3 frames): 5M para 720p, 10M para 1080p
            rtbuf = "5M" if "720" in video_size else "10M"
            dshow_args += ["-rtbufsize", rtbuf]

            # Negociación defensiva NV12: solicitar pin nativo NV12
            # Si el dispositivo no soporta NV12, el retry handler (dshow_options_failed) reentrará sin -pixel_format
            if not dshow_options_failed and cfg.get("enable_nv12_pin", True):
                dshow_args += ["-pixel_format", "nv12"]

        if not dshow_options_failed:
            dshow_args += [
                "-video_size",
                video_size,
                "-framerate",
                str(fps),
            ]

        # Erradicación de deriva de reloj (Clock Drift) de webcam UVC en DirectShow:
        if zerolatency:
            dshow_args += [
                "-use_video_device_timestamps",
                "0",
            ]

        dshow_args += ["-i", f"video={escaped_device}"]
        cmd += dshow_args
        if dshow_options_failed:
            w, h = video_size.split("x") if "x" in video_size else ("1280", "720")
            aspect_filter = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
            cmd += ["-vf", aspect_filter, "-r", str(fps)]

    # Sincronización de framerate de salida:
    # cfr garantiza timestamps estrictamente crecientes (monótonos) a 1/fps exactos,
    # erradicando duplicados de reloj DirectShow y advertencias de Non-monotonic DTS.
    cmd += ["-fps_mode", "cfr"]

    protocol = str(cfg.get("protocol", "udp") or "udp").replace("\x00", "").strip()

    if force_cpu:
        encoder = "libx264"
    else:
        encoder = str(cfg.get("encoder", "auto") or "libx264").replace("\x00", "").strip()
        if encoder == "auto":
            if proc and proc.per_stream_encoder:
                encoder = proc.per_stream_encoder
            elif best_encoder_getter:
                encoder = await best_encoder_getter()
            else:
                encoder = await hardware_detector.get_best_encoder()
            if proc:
                proc.per_stream_encoder = encoder

    # Compatibilidad MediaMTX SRT/MPEG-TS:
    # MediaMTX (gosrt) no soporta demuxing de AV1 dentro de contenedores MPEG-TS estándar.
    # Si se selecciona AV1 con SRT, registramos advertencia técnica clara sin alterar el encoder solicitado.
    if protocol == "srt" and "av1" in str(encoder):
        logger.warning(
            f"AV1 ({encoder}) puede experimentar incompatibilidad con MediaMTX sobre transporte MPEG-TS/SRT. "
            "Se recomienda HEVC (hevc_nvenc) o H.264 para compatibilidad total con MediaMTX."
        )

    pix_fmt = (
        "nv12"
        if (zerolatency or "nvenc" in str(encoder) or "amf" in str(encoder) or "qsv" in str(encoder))
        else "yuv420p"
    )
    cmd += ["-pix_fmt", pix_fmt]

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
                "-keyint_min",
                str(gop),
                "-sc_threshold",
                "0",
                "-bf",
                "0",
                "-threads",
                "4",
                "-slices",
                "4",
                "-x264-params",
                "repeat-headers=1:intra-refresh=1:sliced-threads=1",
                "-flags",
                "+low_delay",
            ]
        elif encoder == "libx265":
            cmd += [
                "-c:v",
                "libx265",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-bf",
                "0",
                "-x265-params",
                "no-scenecut=1:repeat-headers=1",
            ]
        elif encoder in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
            cmd += [
                "-c:v",
                encoder,
                "-preset",
                "p1",
                "-tune",
                "ull",
                "-rc",
                "cbr",
                "-multipass",
                "disabled",
                "-delay",
                "0",
                "-zerolatency",
                "1",
                "-forced-idr",
                "1",
                "-bf",
                "0",
                "-spatial-aq",
                "0",
                "-temporal-aq",
                "0",
                "-surfaces",
                "2",
                "-no-scenecut",
                "1",
                "-rc-lookahead",
                "0",
            ]
            if encoder != "av1_nvenc":
                cmd += ["-b_adapt", "0"]
        elif encoder in ("h264_amf", "hevc_amf", "av1_amf"):
            cmd += [
                "-c:v",
                encoder,
                "-usage",
                "ultralowlatency",
                "-quality",
                "speed",
                "-latency",
                "1",
                "-rc",
                "cbr",
                "-forced_idr",
                "1",
                "-async_depth",
                "1",
                "-bf",
                "0",
                "-max_b_frames",
                "0",
                "-preanalysis",
                "0",
                "-pa_lookahead_buffer_depth",
                "0",
                "-pa_scene_change_detection_enable",
                "0",
                "-header_spacing",
                "0",
                "-enforce_hrd",
                "1",
            ]
        elif encoder in ("h264_qsv", "hevc_qsv", "av1_qsv"):
            cmd += [
                "-c:v",
                encoder,
                "-preset",
                "veryfast",
                "-async_depth",
                "1",
                "-bf",
                "0",
                "-look_ahead",
                "0",
                "-forced_idr",
                "1",
                "-low_delay_brc",
                "1",
                "-scenario",
                "livestreaming",
                "-max_dec_frame_buffering",
                "1",
            ]
        else:
            cmd += ["-c:v", encoder, "-bf", "0"]
    else:
        # Perfil equilibrado de broadcast (sin comprometer calidad innecesariamente)
        if encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-x264-params", "repeat-headers=1"]
        elif encoder == "libx265":
            cmd += ["-c:v", "libx265", "-preset", "veryfast", "-x265-params", "repeat-headers=1"]
        elif encoder in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
            cmd += ["-c:v", encoder, "-preset", "p4", "-tune", "hq", "-forced-idr", "1"]
        elif encoder in ("h264_amf", "hevc_amf", "av1_amf"):
            cmd += ["-c:v", encoder, "-quality", "balanced"]
        elif encoder in ("h264_qsv", "hevc_qsv", "av1_qsv"):
            cmd += ["-c:v", encoder, "-preset", "medium"]
        else:
            cmd += ["-c:v", encoder]

    cmd += ["-b:v", bk, "-maxrate", maxbk, "-bufsize", bufk, "-g", str(gop), "-an"]

    port = cfg.get("port", 9000)
    passphrase = cfg.get("srt_passphrase", "")
    srt_lat = cfg.get("srt_latency")
    # En modo zerolatency el buffer se calibra automáticamente a 10 ms para loopback localhost
    # (absorbe jitter del planificador de Windows sin retardo artificial);
    # si zerolatency está deshabilitado, se respeta la latencia manual definida por el usuario.
    latency_ms = 10 if zerolatency else (int(srt_lat) if srt_lat is not None else 120)
    cam_id = cfg.get("id") or cfg.get("camera_id") or f"cam_{port}"
    clean_cam_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(cam_id))

    if protocol == "srt":
        from core.mediamtx_mgr import mediamtx_manager

        mediamtx_port = mediamtx_manager.get_srt_port()
        # En arquitectura desacoplada con MediaMTX (v2.8.2), FFmpeg publica localmente
        # por loopback (127.0.0.1) sin frase de paso para evitar rechazo BADSECRET.
        # En publicación loopback con zerolatency activo, la latencia de buffer se calibra
        # automáticamente en 10 ms (latency=10000) y tlpktdrop=1 (requerido por gosrt para evitar ERROR:ROGUE).
        effective_srt_latency = 10 if zerolatency else (int(srt_lat) if srt_lat is not None else 20)
        raw_url = build_stream_url(
            protocol="srt",
            port=mediamtx_port,
            passphrase="",
            mode="caller",
            latency_ms=effective_srt_latency,
            zerolatency=zerolatency,
            streamid=f"publish:{clean_cam_id}",
        )
    elif protocol == "rtp":
        udp_host = (cfg.get("udp_host") or "127.0.0.1").strip()
        raw_url = f"rtp://{udp_host}:{port}"
    else:
        udp_mode = cfg.get("udp_mode", "unicast")
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

    if protocol == "rtp":
        cmd += ["-f", "rtp", "-payload_type", "96", raw_url]
    elif zerolatency:
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
            "-pes_payload_size",
            "0",
            raw_url,
        ]
    else:
        cmd += ["-bsf:v", "dump_extra", "-f", "mpegts", raw_url]

    sanitized_url = sanitize_url(raw_url)
    return cmd, sanitized_url, encoder


# Alias canónico
build_command = build_ffmpeg_command


class CommandBuilder:
    """Constructor y validador modular de comandos de transmisión FFmpeg."""

    @staticmethod
    async def build_command(
        cfg: Dict[str, Any],
        force_cpu: bool = False,
        proc: Optional[StreamProc] = None,
        best_encoder_getter: Optional[Callable[[], Any]] = None,
    ) -> Tuple[List[str], str, str]:
        return await build_ffmpeg_command(cfg, force_cpu=force_cpu, proc=proc, best_encoder_getter=best_encoder_getter)

    build_ffmpeg_command = build_command
