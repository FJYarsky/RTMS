# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas de la tubería de streaming y parámetros de ultra baja latencia.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas para validar parámetros de ultra baja latencia en todos los protocolos y codificadores."""

import os
import urllib.parse

import pytest

from core.command_builder import build_ffmpeg_command
from core.latency_bench import LatencyBenchmarkEngine
from core.mediamtx_mgr import mediamtx_manager
from core.stream_proc import (
    build_client_urls,
    build_multicast_url,
    build_stream_url,
    build_unicast_url,
)


@pytest.mark.asyncio
async def test_directshow_zerolatency_flags():
    """Valida los flags de FFmpeg para DirectShow cuando zerolatency=True."""
    cfg = {
        "device_path": "Integrated Camera",
        "friendly_name": "Webcam Pro",
        "resolution": "1080p",
        "fps": 30,
        "bitrate": 4000,
        "protocol": "srt",
        "port": 9000,
        "encoder": "libx264",
        "zerolatency": True,
        "use_mjpeg_input": True,
    }
    cmd, url, enc = await build_ffmpeg_command(cfg, force_cpu=True)

    # Flags globales/demuxer para baja latencia
    assert "-fflags" in cmd
    fflags_idx = cmd.index("-fflags")
    assert "nobuffer+discardcorrupt" in cmd[fflags_idx + 1]

    assert "-flags" in cmd
    flags_idx = cmd.index("-flags")
    assert "low_delay" in cmd[flags_idx + 1]

    assert "-avioflags" in cmd
    avio_idx = cmd.index("-avioflags")
    assert "direct" in cmd[avio_idx + 1]

    assert "-probesize" in cmd
    probe_idx = cmd.index("-probesize")
    assert cmd[probe_idx + 1] == "32"

    assert "-analyzeduration" in cmd
    analyze_idx = cmd.index("-analyzeduration")
    assert cmd[analyze_idx + 1] == "0"

    # DirectShow flags
    assert "-rtbufsize" in cmd
    rtbuf_idx = cmd.index("-rtbufsize")
    assert cmd[rtbuf_idx + 1] == "3M"  # MJPEG (v2.8.2)

    assert "-use_video_device_timestamps" in cmd
    ts_idx = cmd.index("-use_video_device_timestamps")
    assert cmd[ts_idx + 1] == "0"

    # Muxer MPEG-TS flags
    assert "-muxdelay" in cmd
    muxdelay_idx = cmd.index("-muxdelay")
    assert cmd[muxdelay_idx + 1] == "0"

    assert "-muxpreload" in cmd
    muxpreload_idx = cmd.index("-muxpreload")
    assert cmd[muxpreload_idx + 1] == "0"

    assert "-flush_packets" in cmd
    flush_idx = cmd.index("-flush_packets")
    assert cmd[flush_idx + 1] == "1"

    assert "-pat_period" in cmd
    assert "-pcr_period" in cmd
    assert "-bsf:v" in cmd
    assert "dump_extra" in cmd


@pytest.mark.asyncio
async def test_directshow_raw_uncompressed_rtbuf():
    """Valida que entradas no comprimidas (use_mjpeg_input=False) utilicen buffer calibrado (5M para 720p)."""
    cfg = {
        "device_path": "HDMI Capture Card",
        "resolution": "720p",
        "fps": 60,
        "protocol": "srt",
        "encoder": "libx264",
        "zerolatency": True,
        "use_mjpeg_input": False,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)
    rtbuf_idx = cmd.index("-rtbufsize")
    assert cmd[rtbuf_idx + 1] == "5M"


@pytest.mark.asyncio
@pytest.mark.parametrize("enc", ["h264_nvenc", "hevc_nvenc", "av1_nvenc"])
async def test_nvenc_zerolatency_flags(enc):
    """Valida los flags de ultra baja latencia para la familia de codificadores NVENC."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "1080p",
        "fps": 60,
        "protocol": "srt",
        "encoder": enc,
        "zerolatency": True,
    }
    cmd, _, chosen_enc = await build_ffmpeg_command(cfg)
    assert chosen_enc == enc

    # Verificar 0 B-frames y cero delay
    assert "-delay" in cmd
    delay_idx = cmd.index("-delay")
    assert cmd[delay_idx + 1] == "0"

    assert "-zerolatency" in cmd
    zl_idx = cmd.index("-zerolatency")
    assert cmd[zl_idx + 1] == "1"

    assert "-bf" in cmd
    bf_idx = cmd.index("-bf")
    assert cmd[bf_idx + 1] == "0"

    assert "-rc-lookahead" in cmd
    rc_la_idx = cmd.index("-rc-lookahead")
    assert cmd[rc_la_idx + 1] == "0"

    assert "-forced-idr" in cmd
    assert "-surfaces" in cmd
    assert "-tune" in cmd
    assert "ull" in cmd


@pytest.mark.asyncio
@pytest.mark.parametrize("enc", ["h264_qsv", "hevc_qsv", "av1_qsv"])
async def test_qsv_zerolatency_flags(enc):
    """Valida los flags de ultra baja latencia para la familia de codificadores Intel QSV."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": 30,
        "protocol": "srt",
        "encoder": enc,
        "zerolatency": True,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg)

    assert "-preset" in cmd
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "veryfast"

    assert "-async_depth" in cmd
    async_idx = cmd.index("-async_depth")
    assert cmd[async_idx + 1] == "1"

    assert "-bf" in cmd
    bf_idx = cmd.index("-bf")
    assert cmd[bf_idx + 1] == "0"

    assert "-look_ahead" in cmd
    la_idx = cmd.index("-look_ahead")
    assert cmd[la_idx + 1] == "0"

    assert "-forced_idr" in cmd


@pytest.mark.asyncio
@pytest.mark.parametrize("enc", ["h264_amf", "hevc_amf", "av1_amf"])
async def test_amf_zerolatency_flags(enc):
    """Valida los flags de ultra baja latencia para la familia de codificadores AMD AMF."""
    cfg = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": 30,
        "protocol": "srt",
        "encoder": enc,
        "zerolatency": True,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg)

    assert "-quality" in cmd
    qual_idx = cmd.index("-quality")
    assert cmd[qual_idx + 1] == "speed"

    assert "-usage" in cmd
    usage_idx = cmd.index("-usage")
    assert cmd[usage_idx + 1] == "ultralowlatency"

    assert "-async_depth" in cmd
    async_idx = cmd.index("-async_depth")
    assert cmd[async_idx + 1] == "1"

    assert "-bf" in cmd
    bf_idx = cmd.index("-bf")
    assert cmd[bf_idx + 1] == "0"

    assert "-preanalysis" in cmd
    pa_idx = cmd.index("-preanalysis")
    assert cmd[pa_idx + 1] == "0"

    assert "-forced_idr" in cmd


@pytest.mark.asyncio
async def test_libx264_and_libx265_zerolatency_flags():
    """Valida los flags de ultra baja latencia para CPU libx264 y libx265."""
    for enc, param_key in [("libx264", "-x264-params"), ("libx265", "-x265-params")]:
        cfg = {
            "device_path": "virtual://test",
            "resolution": "720p",
            "fps": 30,
            "protocol": "srt",
            "encoder": enc,
            "zerolatency": True,
        }
        cmd, _, _ = await build_ffmpeg_command(cfg)

        assert "-preset" in cmd
        p_idx = cmd.index("-preset")
        assert cmd[p_idx + 1] == "ultrafast"

        assert "-tune" in cmd
        t_idx = cmd.index("-tune")
        assert cmd[t_idx + 1] == "zerolatency"

        assert "-bf" in cmd
        bf_idx = cmd.index("-bf")
        assert cmd[bf_idx + 1] == "0"

        assert param_key in cmd


def test_srt_url_zerolatency_parameters():
    """Valida que la URL de SRT en modo zerolatency tenga latency=10000, tlpktdrop=1, sndbuf=65536, rcvbuf=65536."""
    url = build_stream_url(
        protocol="srt",
        port=8890,
        mode="caller",
        zerolatency=True,
        streamid="publish:cam_1",
    )
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    assert qs["latency"][0] == "10000"
    assert qs["tlpktdrop"][0] == "1"
    assert qs["sndbuf"][0] == "65536"
    assert qs["rcvbuf"][0] == "65536"
    assert qs["mode"][0] == "caller"
    assert qs["streamid"][0] == "publish:cam_1"


def test_srt_url_broadcast_parameters():
    """Valida que la URL de SRT en modo broadcast (zerolatency=False) use buffers amplios."""
    url = build_stream_url(
        protocol="srt",
        port=8890,
        mode="listener",
        latency_ms=200,
        zerolatency=False,
    )
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    assert qs["latency"][0] == "200000"
    assert qs["tlpktdrop"][0] == "0"
    assert qs["sndbuf"][0] == "262144"
    assert qs["rcvbuf"][0] == "262144"
    assert qs.get("smoother", [None])[0] == "live"


def test_udp_low_latency_parameters():
    """Valida parámetros de ultra baja latencia para UDP unicast y multicast."""
    u_url = build_unicast_url(9000, "127.0.0.1")
    assert "pkt_size=1316" in u_url
    assert "buffer_size=65536" in u_url
    assert "overrun_nonfatal=1" in u_url
    assert "fifo_size=5000" in u_url

    m_url = build_multicast_url(9001)
    assert "239.255.0.2:9001" in m_url
    assert "ttl=16" in m_url
    assert "pkt_size=1316" in m_url
    assert "buffer_size=65536" in m_url
    assert "overrun_nonfatal=1" in m_url


def test_client_vlc_low_latency_caching():
    """Valida que los comandos generados para VLC usen búfer seguro de 300 ms sin directivas desestabilizadoras."""
    res_srt = build_client_urls("srt", "127.0.0.1", 9000, "cam_test")
    assert ":network-caching=300" in res_srt["vlc_command"]
    assert ":clock-jitter=0" not in res_srt["vlc_command"]
    assert ":clock-synchro=0" not in res_srt["vlc_command"]
    assert res_srt["vlc_caching_ms"] == 300

    res_custom = build_client_urls("srt", "127.0.0.1", 9000, "cam_test", latency_ms=250)
    assert ":network-caching=300" in res_custom["vlc_command"]
    assert res_custom["vlc_caching_ms"] == 300
    assert ":clock-jitter=0" not in res_custom["vlc_command"]

    res_udp = build_client_urls("udp", "127.0.0.1", 9000, "cam_test", udp_mode="multicast")
    assert ":network-caching=300" in res_udp["vlc_command"]
    assert ":clock-jitter=0" not in res_udp["vlc_command"]
    assert ":clock-synchro=0" not in res_udp["vlc_command"]
    assert "udp://@239.255.0.1:9000" in res_udp["vlc_url"]


def test_mediamtx_config_anti_buffering():
    """Valida que la configuración dinámica de MediaMTX incorpore writeQueueSize y overridePublisher."""
    cfg_path = mediamtx_manager.generate_config(srt_port=8890)
    assert os.path.exists(cfg_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "writeQueueSize: 128" in content
    assert "udpMaxPayloadSize: 1472" in content
    assert "overridePublisher: yes" in content
    assert "webrtc: yes" in content
    assert "srt: yes" in content


def test_latency_bench_socket_ping():
    """Valida la ejecución del benchmark de ping UDP en loopback."""
    stats = LatencyBenchmarkEngine.measure_udp_socket_ping(port=9877, iterations=10, timeout=0.05)
    assert stats.protocol == "udp_loopback"
    assert stats.samples_count >= 0
    if stats.samples_count > 0:
        assert stats.min_ms >= 0.0
        assert stats.avg_ms >= 0.0
        assert stats.jitter_ms >= 0.0
