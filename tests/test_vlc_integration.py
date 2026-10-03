# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de integración de extremo a extremo con cliente VLC Media Player.
# Verifica que VLC entable comunicación de forma correcta para todas las
# configuraciones y protocolos del software:
# 1. SRT sin encriptar (Caller -> MediaMTX -> VLC Reader).
# 2. SRT con cifrado AES / passphrase (Caller -> MediaMTX -> VLC Reader).
# 3. UDP Multicast (Mapeo inyectivo 239.255.0.x).
# 4. UDP Unicast (@:puerto).
# 5. Códec HEVC / H.265 sobre SRT de baja latencia.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de validación de compatibilidad y decodificación con VLC Media Player."""

import asyncio
import os
import subprocess
from typing import Any, Dict

import pytest

from core.hardware import get_ffmpeg_bin
from core.mediamtx_mgr import mediamtx_manager

VLC_PATH = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
HAS_VLC = os.path.exists(VLC_PATH)


def run_vlc_probe(url: str, runtime_sec: int = 3, timeout_sec: int = 7) -> Dict[str, Any]:
    """Ejecuta VLC contra una URL y analiza los logs de stderr para verificar conexión y decodificación."""
    vlc_cmd = [
        VLC_PATH,
        "-I",
        "dummy",
        "-vvv",
        url,
        ":network-caching=150",
        "vlc://quit",
        f"--run-time={runtime_sec}",
    ]
    p = subprocess.Popen(vlc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    try:
        _, err = p.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        p.kill()
        _, err = p.communicate()

    err_lower = err.lower()
    connected = any(
        k in err_lower
        for k in [
            "connected",
            "connection established",
            "access_srt",
            "using access module",
            "incoming stream",
        ]
    )
    has_demux = any(k in err_lower for k in ["ts demux", "mpeg-ts", "ts packet", "demux"])
    has_codec = any(k in err_lower for k in ["h264", "hevc", "h265", "avcodec"])
    received_data = any(k in err_lower for k in ["packet", "buffer", "video", "received first data"])

    return {
        "url": url,
        "success": (has_demux or has_codec) and received_data,
        "connected": connected,
        "demux_detected": has_demux,
        "codec_detected": has_codec,
        "received_data": received_data,
    }


@pytest.mark.skipif(not HAS_VLC, reason="VLC no está instalado en el sistema")
@pytest.mark.asyncio
async def test_vlc_srt_unencrypted():
    """Valida que VLC reciba y decodifique video H.264 sobre SRT sin cifrado vía MediaMTX."""
    ffmpeg_bin = get_ffmpeg_bin()
    await mediamtx_manager.start(srt_port=8890)
    await asyncio.sleep(0.5)

    cam_id = "vlc_test_srt_plain"
    pub_url = f"srt://127.0.0.1:8890?streamid=publish:{cam_id}&latency=120000&tlpktdrop=1"
    vlc_url = f"srt://127.0.0.1:8890?streamid=read:{cam_id}"

    ff_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-f",
        "mpegts",
        pub_url,
    ]
    ff = subprocess.Popen(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.2)
        res = run_vlc_probe(vlc_url, runtime_sec=3)
        assert res["success"] is True
        assert res["demux_detected"] is True
    finally:
        ff.terminate()
        ff.wait(timeout=2)
        mediamtx_manager.stop()


@pytest.mark.skipif(not HAS_VLC, reason="VLC no está instalado en el sistema")
@pytest.mark.asyncio
async def test_vlc_srt_encrypted():
    """Valida que VLC reciba y decodifique video H.264 sobre SRT cifrado con passphrase."""
    ffmpeg_bin = get_ffmpeg_bin()
    await mediamtx_manager.start(srt_port=8890)
    await asyncio.sleep(0.5)

    cam_id = "vlc_test_srt_crypt"
    secret = "rtms_passphrase_test_123"
    await mediamtx_manager.sync_path_api(cam_id, secret)
    await asyncio.sleep(0.3)

    pub_url = f"srt://127.0.0.1:8890?streamid=publish:{cam_id}&passphrase={secret}&latency=120000&tlpktdrop=1"
    vlc_url = f"srt://127.0.0.1:8890?streamid=read:{cam_id}&passphrase={secret}"

    ff_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-f",
        "mpegts",
        pub_url,
    ]
    ff = subprocess.Popen(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.2)
        res = run_vlc_probe(vlc_url, runtime_sec=3)
        assert res["success"] is True
        assert res["codec_detected"] is True
    finally:
        ff.terminate()
        ff.wait(timeout=2)
        mediamtx_manager.stop()


@pytest.mark.skipif(not HAS_VLC, reason="VLC no está instalado en el sistema")
@pytest.mark.asyncio
async def test_vlc_udp_multicast():
    """Valida que VLC reciba y decodifique video sobre UDP Multicast (239.255.0.x)."""
    ffmpeg_bin = get_ffmpeg_bin()
    port = 9005
    mc_ip = "239.255.0.6"
    dest_url = f"udp://{mc_ip}:{port}?pkt_size=1316&buffer_size=65535"
    vlc_url = f"udp://@{mc_ip}:{port}"

    ff_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-f",
        "mpegts",
        dest_url,
    ]
    ff = subprocess.Popen(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.0)
        res = run_vlc_probe(vlc_url, runtime_sec=3)
        assert res["success"] is True
        assert res["demux_detected"] is True
    finally:
        ff.terminate()
        ff.wait(timeout=2)


@pytest.mark.skipif(not HAS_VLC, reason="VLC no está instalado en el sistema")
@pytest.mark.asyncio
async def test_vlc_udp_unicast():
    """Valida que VLC reciba y decodifique video sobre UDP Unicast local."""
    ffmpeg_bin = get_ffmpeg_bin()
    port = 9015
    dest_url = f"udp://127.0.0.1:{port}?pkt_size=1316&buffer_size=65535"
    vlc_url = f"udp://@:{port}"

    ff_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-f",
        "mpegts",
        dest_url,
    ]
    ff = subprocess.Popen(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.0)
        res = run_vlc_probe(vlc_url, runtime_sec=3)
        assert res["success"] is True
        assert res["codec_detected"] is True
    finally:
        ff.terminate()
        ff.wait(timeout=2)


@pytest.mark.skipif(not HAS_VLC, reason="VLC no está instalado en el sistema")
@pytest.mark.asyncio
async def test_vlc_hevc_over_srt():
    """Valida que VLC reciba y decodifique video codificado en HEVC / H.265 sobre SRT."""
    ffmpeg_bin = get_ffmpeg_bin()
    await mediamtx_manager.start(srt_port=8890)
    await asyncio.sleep(0.5)

    cam_id = "vlc_test_hevc"
    pub_url = f"srt://127.0.0.1:8890?streamid=publish:{cam_id}&latency=120000&tlpktdrop=1"
    vlc_url = f"srt://127.0.0.1:8890?streamid=read:{cam_id}"

    ff_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-an",
        "-c:v",
        "libx265",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-f",
        "mpegts",
        pub_url,
    ]
    ff = subprocess.Popen(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.5)
        res = run_vlc_probe(vlc_url, runtime_sec=3)
        assert res["success"] is True
        assert res["codec_detected"] is True
    finally:
        ff.terminate()
        ff.wait(timeout=2)
        mediamtx_manager.stop()


def test_generate_vlc_xspf_playlist():
    """Valida que la lista de reproducción XSPF se genere con formato XML válido y opciones VLC de 50ms."""
    from core.stream_proc import generate_vlc_xspf_playlist

    xml = generate_vlc_xspf_playlist(
        stream_url="srt://127.0.0.1:8890?streamid=read:cam_01",
        title="Cámara 1 & Principal <Test>",
        caching_ms=50,
    )

    assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
    assert '<playlist version="1"' in xml
    assert "network-caching=50" in xml
    assert "clock-jitter=0" not in xml
    assert "clock-synchro=0" not in xml
    assert "drop-late-frames" in xml
    assert "&amp;" in xml  # Caracteres especiales escapados correctamente


def test_launch_vlc_player_mocked(monkeypatch):
    """Valida la invocación de proceso de VLC con parámetros forzados de baja latencia."""
    from unittest.mock import MagicMock

    from core.stream_proc import launch_vlc_player

    monkeypatch.setattr("core.stream_proc.get_vlc_binary_path", lambda: r"C:\Fake\vlc.exe")
    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    res = launch_vlc_player("udp://@239.255.0.1:9000", caching_ms=50)
    assert res is True
    assert mock_popen.called
    args = mock_popen.call_args[0][0]
    assert args[0] == r"C:\Fake\vlc.exe"
    assert args[1] == "udp://@239.255.0.1:9000"
    assert ":network-caching=50" in args
    assert ":clock-jitter=0" not in args
    assert ":clock-synchro=0" not in args


@pytest.mark.asyncio
async def test_api_vlc_endpoints():
    """Valida los endpoints REST /api/stream/.../vlc_playlist.xspf y /launch_vlc."""
    from unittest.mock import MagicMock

    from httpx import ASGITransport, AsyncClient

    from main import create_app

    test_token = "test_token_vlc_12345678"
    app = create_app(token=test_token)

    from core.config_mgr import load_config, save_config

    cfg = load_config()
    cfg["cameras"]["@device:pnp:vlc_test_cam"] = {
        "device_path": "@device:pnp:vlc_test_cam",
        "friendly_name": "VLC Test Cam",
        "protocol": "srt",
        "port": 9015,
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2500,
        "zerolatency": True,
    }
    save_config(cfg)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"X-RTMS-Token": test_token}

        # 1. Probar connect_url enriquecido con opciones VLC
        res_conn = await ac.get("/api/stream/%40device%3Apnp%3Avlc_test_cam/connect_url", headers=headers)
        assert res_conn.status_code == 200
        data_conn = res_conn.json()
        assert "vlc_command" in data_conn
        assert "vlc_caching_ms" in data_conn
        assert data_conn["vlc_caching_ms"] == 300

        # 2. Probar descarga de playlist .xspf
        res_xspf = await ac.get("/api/stream/%40device%3Apnp%3Avlc_test_cam/vlc_playlist.xspf", headers=headers)
        assert res_xspf.status_code == 200
        assert res_xspf.headers["content-type"].startswith("application/xspf+xml")
        assert "attachment" in res_xspf.headers["content-disposition"]
        assert "network-caching=300" in res_xspf.text

        # 3. Probar launch_vlc con mock de ejecución
        import core.stream_proc

        original_launch = core.stream_proc.launch_vlc_player
        original_get_bin = core.stream_proc.get_vlc_binary_path
        core.stream_proc.launch_vlc_player = MagicMock(return_value=True)
        core.stream_proc.get_vlc_binary_path = MagicMock(return_value=r"C:\Program Files\VideoLAN\VLC\vlc.exe")
        try:
            res_launch = await ac.post("/api/stream/%40device%3Apnp%3Avlc_test_cam/launch_vlc", headers=headers)
            assert res_launch.status_code == 200
            assert res_launch.json()["status"] == "ok"

            # 4. Probar launch_vlc cuando VLC no está instalado
            core.stream_proc.get_vlc_binary_path = MagicMock(return_value=None)
            res_no_vlc = await ac.post("/api/stream/%40device%3Apnp%3Avlc_test_cam/launch_vlc", headers=headers)
            assert res_no_vlc.status_code == 400
            assert "no se encuentra instalado" in res_no_vlc.json()["detail"]
        finally:
            core.stream_proc.launch_vlc_player = original_launch
            core.stream_proc.get_vlc_binary_path = original_get_bin


@pytest.mark.asyncio
async def test_command_builder_nvenc_ultra_low_latency():
    """Valida que el constructor de comandos inyecte banderas completas de ultra baja latencia para NVENC."""
    from core.command_builder import build_ffmpeg_command

    cfg = {
        "device_path": "@device_nvenc_test",
        "friendly_name": "NVENC Cam",
        "resolution": "720p",
        "fps": 60,
        "bitrate": 4000,
        "protocol": "srt",
        "port": 9020,
        "encoder": "h264_nvenc",
        "zerolatency": True,
    }
    cmd, url, enc = await build_ffmpeg_command(cfg)

    assert "-tune" in cmd
    assert "ull" in cmd  # Ultra low latency
    assert "-multipass" in cmd and "disabled" in cmd
    assert "-delay" in cmd and "0" in cmd
    assert "-surfaces" in cmd and "2" in cmd
    assert "-rc-lookahead" in cmd and "0" in cmd
    assert "-temporal-aq" in cmd and "0" in cmd
    assert "-spatial-aq" in cmd and "0" in cmd
    assert "-no-scenecut" in cmd and "1" in cmd


@pytest.mark.asyncio
async def test_command_builder_av1_nvenc_flags():
    """Valida que selecciones de AV1 NVENC generen el códec av1_nvenc con banderas de baja latencia."""
    from core.command_builder import build_ffmpeg_command

    cfg = {
        "device_path": "@device_av1_test",
        "friendly_name": "AV1 Cam",
        "resolution": "1080p",
        "fps": 30,
        "bitrate": 3000,
        "protocol": "srt",
        "port": 9022,
        "encoder": "av1_nvenc",
        "zerolatency": True,
    }
    cmd, url, enc = await build_ffmpeg_command(cfg)

    assert enc == "av1_nvenc"
    assert "av1_nvenc" in cmd
    assert "-tune" in cmd
    assert "ull" in cmd


@pytest.mark.asyncio
async def test_command_builder_directshow_low_latency_timestamps():
    """Valida que DirectShow elimine la deriva de reloj e inyecte rtbufsize dinámico."""
    from core.command_builder import build_ffmpeg_command

    cfg = {
        "device_path": "@device_pnp_webcam",
        "friendly_name": "Webcam UVC",
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2000,
        "protocol": "srt",
        "port": 9024,
        "encoder": "libx264",
        "use_mjpeg_input": True,
        "zerolatency": True,
    }
    cmd, url, enc = await build_ffmpeg_command(cfg)

    # Debe contener -use_video_device_timestamps 0
    assert "-use_video_device_timestamps" in cmd
    idx = cmd.index("-use_video_device_timestamps")
    assert cmd[idx + 1] == "0"

    # En MJPEG el rtbufsize debe ser 3M (v2.8.2)
    assert "3M" in cmd

    # Probesize y analyzeduration mínimos
    assert "-probesize" in cmd and "32" in cmd
    assert "-analyzeduration" in cmd and "0" in cmd
