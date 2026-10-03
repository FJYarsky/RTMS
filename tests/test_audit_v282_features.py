# ==============================================================================
# RTMS — Real-Time Multicam System
# Suite de pruebas automatizadas de validación y regresión para versión 2.8.2.
# Verifica todas las optimizaciones extremas de baja latencia y criterios de aceptación.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias y de integración para las características de RTMS v2.8.2."""

import os
import tomllib
import urllib.parse

import pytest

from core.__version__ import __version__
from core.command_builder import build_ffmpeg_command
from core.hardware import DirectShowDeviceScanner
from core.mediamtx_mgr import _WIN_FLAGS as MTX_WIN_FLAGS
from core.mediamtx_mgr import mediamtx_manager
from core.preview_mgr import PreviewManager
from core.process_optimizer import HIGH_PRIORITY_CLASS, elevate_process_priority
from core.stream_manager import _WIN_FLAGS as STREAM_WIN_FLAGS
from core.stream_proc import build_client_urls, build_stream_url
from core.telemetry import telemetry_service


def test_v282_version_bump_consistency():
    """Valida que la versión 2.8.2+ esté sincronizada en __version__.py, pyproject.toml y config.example.json."""
    assert __version__ in ("2.8.2", "2.8.3")

    pyproject_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
    assert pyproject_data["project"]["version"] in ("2.8.2", "2.8.3")

    config_ex_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.example.json"
    )
    import json

    with open(config_ex_path, "r", encoding="utf-8") as f:
        config_ex = json.load(f)
    assert config_ex["version"] in ("2.8.2", "2.8.3")


@pytest.mark.asyncio
async def test_v282_directshow_nv12_and_cfr():
    """Valida que entradas DirectShow en zerolatency soliciten pixel_format nv12 y fps_mode cfr para timestamps monótonos."""
    cfg = {
        "device_path": "Webcam Pro HD",
        "resolution": "1080p",
        "fps": 60,
        "protocol": "srt",
        "encoder": "libx264",
        "zerolatency": True,
        "use_mjpeg_input": False,
        "enable_nv12_pin": True,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)

    assert "-pixel_format" in cmd
    pf_idx = cmd.index("-pixel_format")
    assert cmd[pf_idx + 1] == "nv12"

    assert "-fps_mode" in cmd
    fps_mode_idx = cmd.index("-fps_mode")
    assert cmd[fps_mode_idx + 1] == "cfr"


@pytest.mark.asyncio
async def test_v282_rtbufsize_sizing_calibration():
    """Valida que rtbufsize se calibre a 10M para 1080p, 5M para 720p y 3M para MJPEG."""
    # 1080p uncompressed
    cfg_1080p = {
        "device_path": "Webcam 1080p",
        "resolution": "1080p",
        "fps": 60,
        "zerolatency": True,
        "use_mjpeg_input": False,
    }
    cmd_1080p, _, _ = await build_ffmpeg_command(cfg_1080p, force_cpu=True)
    idx_1080 = cmd_1080p.index("-rtbufsize")
    assert cmd_1080p[idx_1080 + 1] == "10M"

    # 720p uncompressed
    cfg_720p = {
        "device_path": "Webcam 720p",
        "resolution": "720p",
        "fps": 60,
        "zerolatency": True,
        "use_mjpeg_input": False,
    }
    cmd_720p, _, _ = await build_ffmpeg_command(cfg_720p, force_cpu=True)
    idx_720 = cmd_720p.index("-rtbufsize")
    assert cmd_720p[idx_720 + 1] == "5M"

    # MJPEG
    cfg_mjpeg = {
        "device_path": "Webcam MJPEG",
        "resolution": "1080p",
        "fps": 30,
        "zerolatency": True,
        "use_mjpeg_input": True,
    }
    cmd_mjpeg, _, _ = await build_ffmpeg_command(cfg_mjpeg, force_cpu=True)
    idx_mjpeg = cmd_mjpeg.index("-rtbufsize")
    assert cmd_mjpeg[idx_mjpeg + 1] == "3M"


@pytest.mark.asyncio
async def test_v282_vbv_rate_control_formula():
    """Valida que el buffer VBV (-bufsize) calcule max(50, bitrate/fps*1.5) en lugar de bitrate*0.35."""
    fps = 60
    bitrate = 3000
    cfg = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": fps,
        "bitrate": bitrate,
        "zerolatency": True,
        "encoder": "libx264",
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)
    buf_idx = cmd.index("-bufsize")
    expected_vbv = f"{max(50, int(bitrate / fps * 1.5))}k"  # 75k
    assert cmd[buf_idx + 1] == expected_vbv


@pytest.mark.asyncio
async def test_v282_libx264_parallel_slices_and_low_delay():
    """Valida que libx264 incorpore slice-threading (-slices 4 -threads 4), flags low_delay e intra-refresh."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": 30,
        "zerolatency": True,
        "encoder": "libx264",
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)

    assert "-slices" in cmd
    slices_idx = cmd.index("-slices")
    assert cmd[slices_idx + 1] == "4"

    assert "-threads" in cmd
    threads_idx = cmd.index("-threads")
    assert cmd[threads_idx + 1] == "4"

    assert "+low_delay" in cmd

    x264_idx = cmd.index("-x264-params")
    x264_params = cmd[x264_idx + 1]
    assert "intra-refresh=1" in x264_params
    assert "sliced-threads=1" in x264_params


@pytest.mark.asyncio
async def test_v282_amf_extreme_low_delay_flags():
    """Valida que h264_amf aplique el conjunto completo de flags de ultra baja latencia."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "1080p",
        "fps": 60,
        "zerolatency": True,
        "encoder": "h264_amf",
    }
    cmd, _, enc = await build_ffmpeg_command(cfg)
    assert enc == "h264_amf"

    assert "-latency" in cmd
    lat_idx = cmd.index("-latency")
    assert cmd[lat_idx + 1] == "1"

    assert "-rc" in cmd
    rc_idx = cmd.index("-rc")
    assert cmd[rc_idx + 1] == "cbr"

    assert "-enforce_hrd" in cmd
    hrd_idx = cmd.index("-enforce_hrd")
    assert cmd[hrd_idx + 1] == "1"

    assert "-header_spacing" in cmd
    hs_idx = cmd.index("-header_spacing")
    assert cmd[hs_idx + 1] == "0"


@pytest.mark.asyncio
async def test_v282_mpegts_pes_payload_size_zero():
    """Valida que el multiplexor MPEG-TS incluya -pes_payload_size 0 para evitar bufferbloat de PES."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": 30,
        "zerolatency": True,
        "protocol": "srt",
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)
    assert "-pes_payload_size" in cmd
    pes_idx = cmd.index("-pes_payload_size")
    assert cmd[pes_idx + 1] == "0"


def test_v282_srt_loopback_and_egress_calibration():
    """Valida que loopback ingest sea 10ms con tlpktdrop=1 (gosrt compatible), y client egress sea 15ms en cableada y 50ms en wifi."""
    # Ingest loopback
    ingest_url = build_stream_url(
        protocol="srt",
        port=8890,
        mode="caller",
        zerolatency=True,
        streamid="publish:cam_main",
    )
    parsed = urllib.parse.urlparse(ingest_url)
    qs = urllib.parse.parse_qs(parsed.query)
    assert qs["latency"][0] == "10000"
    assert qs["tlpktdrop"][0] == "1"

    # Egress Wired
    wired_urls = build_client_urls("srt", "192.168.1.10", 9000, "cam_main", network_type="wired")
    assert "latency=15000" in wired_urls["vlc_url"]
    assert "webrtc" in wired_urls
    assert wired_urls["webrtc"] == "http://192.168.1.10:8889/cam_main"

    # Egress WiFi
    wifi_urls = build_client_urls("srt", "192.168.1.10", 9000, "cam_main", network_type="wifi")
    assert "latency=50000" in wifi_urls["vlc_url"]


def test_v282_mediamtx_config_parameters():
    """Valida que MediaMTX genere writeQueueSize 128, bind a todas las interfaces y host ICE adicional."""
    cfg_file = mediamtx_manager.generate_config(srt_port=8890)
    with open(cfg_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "writeQueueSize: 128" in content
    assert "webrtcAddress: :8889" in content
    assert "webrtcAdditionalHosts:" in content


def test_v282_process_priority_elevation():
    """Valida que core/process_optimizer sea funcional y las banderas de proceso incluyan HIGH_PRIORITY_CLASS."""
    assert (STREAM_WIN_FLAGS & HIGH_PRIORITY_CLASS) == HIGH_PRIORITY_CLASS
    assert (MTX_WIN_FLAGS & HIGH_PRIORITY_CLASS) == HIGH_PRIORITY_CLASS

    # Verificar que elevate_process_priority se pueda invocar sin excepciones
    res = elevate_process_priority(pid=0)
    assert res is False  # PID 0 o no win32 retorna False limpiamente


def test_v282_preview_whep_url_helper():
    """Valida que PreviewManager genere URLs WebRTC WHEP nativas para el navegador."""
    pm = PreviewManager()
    url = pm.get_whep_preview_url("cam_front_1", local_ip="192.168.1.150")
    assert url == "http://192.168.1.150:8889/cam_front_1"


@pytest.mark.asyncio
async def test_v282_telemetry_async_offloading():
    """Valida que SystemTelemetryService provea collect_async no bloqueante."""
    stats = await telemetry_service.collect_async(active_streams_count=1, total_bitrate_kbps=4000.0)
    assert isinstance(stats, dict)
    assert "cpu_percent" in stats
    assert "memory_percent" in stats


def test_v282_hardware_scanner_cache_ttl():
    """Valida que DirectShowDeviceScanner use un TTL de 15.0 segundos por defecto."""
    scanner = DirectShowDeviceScanner()
    assert scanner._cache_ttl == 15.0
