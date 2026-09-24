# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas para las funciones de Fase 3 (v2.6.0).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas unitarias e integración para características introducidas en RTMS v2.6.0."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from core.command_builder import build_ffmpeg_command
from core.config_models import CameraConfig, SystemSettingsConfig
from core.stream_proc import State, StreamProc
from core.telemetry_hub import TelemetryWebSocketHub
from main import create_app


@pytest.fixture
def client():
    app = create_app(token="test_v260_secret_token_123")
    return TestClient(app)


@pytest.mark.asyncio
async def test_command_builder_progress_pipe():
    """Valida que el generador de comandos inyecte -progress pipe:1 -nostats determinista."""
    cmd, url, enc = await build_ffmpeg_command(
        {
            "friendly_name": "Integrated Camera",
            "device_path": "@device:pnp:\\\\?\\usb#vid_...",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "is_virtual": False,
        }
    )
    assert "-progress" in cmd
    idx = cmd.index("-progress")
    assert cmd[idx + 1] == "pipe:1"
    assert "-nostats" in cmd
    assert "-stats" not in cmd


@pytest.mark.asyncio
async def test_command_builder_mjpeg_silicon_negotiation():
    """Valida la inyección de -vcodec mjpeg para webcams físicas USB DirectShow."""
    # Cámara física -> debe tener -vcodec mjpeg antes de -i
    cmd_physical, _, _ = await build_ffmpeg_command(
        {
            "friendly_name": "HD Pro Webcam C920",
            "device_path": "@device_c920",
            "resolution": "1080p",
            "fps": 30,
            "bitrate": 4000,
            "protocol": "srt",
            "port": 9000,
            "is_virtual": False,
        }
    )
    assert "-vcodec" in cmd_physical
    vcodec_idx = cmd_physical.index("-vcodec")
    assert cmd_physical[vcodec_idx + 1] == "mjpeg"
    input_idx = cmd_physical.index("-i")
    assert vcodec_idx < input_idx

    # Dispositivo virtual -> NO debe tener -vcodec mjpeg antes de -i
    cmd_virtual, _, _ = await build_ffmpeg_command(
        {
            "friendly_name": "OBS Virtual Camera",
            "device_path": "virtual://obs_cam",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "is_virtual": True,
        }
    )
    # En virtual el input es lavfi, no DirectShow con -vcodec mjpeg
    assert "testsrc2" in " ".join(cmd_virtual) or "lavfi" in " ".join(cmd_virtual)


@pytest.mark.asyncio
async def test_stream_proc_read_progress():
    """Valida que StreamProc.read_progress parse pares key=value sin scraping regex."""
    proc = StreamProc("@test_cam_progress")
    raw_lines = (
        b"frame=42\n"
        b"fps=29.97\n"
        b"stream_0_0_q=-1.0\n"
        b"bitrate= 3250.4kbits/s\n"
        b"total_size=123456\n"
        b"out_time_us=1500000\n"
        b"out_time=00:00:01.500000\n"
        b"dup_frames=0\n"
        b"drop_frames=3\n"
        b"speed=1.0x\n"
        b"progress=continue\n"
    )

    reader = asyncio.StreamReader()
    reader.feed_data(raw_lines)
    reader.feed_eof()

    await proc.read_progress(reader)

    assert proc.current_fps == 29.97
    assert proc.current_bitrate_kbps == 3250.4
    assert proc.current_speed == "1.0x"
    assert proc.current_dropped_frames == 3
    assert proc.total_frames == 42


def test_config_models_camera_validation():
    """Valida los esquemas estrictos de Pydantic v2 para CameraConfig."""
    valid_cam = CameraConfig(
        friendly_name="Webcam Estudio",
        device_path="@device_cam_valid",
        port=9010,
        resolution="1080p",
        fps=60,
        bitrate=5000,
        protocol="srt",
        encoder="auto",
        srt_passphrase="SecretPassphrase123",
    )
    assert valid_cam.resolution == "1080p"
    assert valid_cam.fps == 60
    assert valid_cam.port == 9010

    # Passphrase demasiado corta (<10 chars)
    with pytest.raises(ValidationError):
        CameraConfig(
            friendly_name="Webcam Invalida",
            device_path="@device_cam_invalid",
            srt_passphrase="short",
        )

    # Resolución inválida
    with pytest.raises(ValidationError):
        CameraConfig(
            friendly_name="Webcam Invalida",
            device_path="@device_cam_invalid",
            resolution="8K",
        )


def test_config_models_system_settings_validation():
    """Valida los esquemas estrictos de Pydantic v2 para SystemSettingsConfig."""
    sys_cfg = SystemSettingsConfig(
        mediamtx_srt_port=8890,
        mediamtx_webrtc_port=8889,
        unattended_autostart=True,
    )
    assert sys_cfg.mediamtx_srt_port == 8890
    assert sys_cfg.mediamtx_webrtc_port == 8889
    assert sys_cfg.unattended_autostart is True

    # Puerto fuera de rango (<1024)
    with pytest.raises(ValidationError):
        SystemSettingsConfig(mediamtx_srt_port=80)


def test_whep_preview_proxy_endpoint(client):
    """Valida el endpoint proxy WHEP anti-CORS POST /api/stream/{device_path}/whep."""
    from core.stream_manager import stream_manager

    dp = "@device_whep_test_cam"
    proc = stream_manager.get_proc(dp)
    proc.config = {"id": "cam_whep_test", "device_path": dp}
    proc.state = State.RUNNING
    proc.process = MagicMock(returncode=None)

    fake_sdp_offer = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
    fake_sdp_answer = "v=0\r\no=MediaMTX 1 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"

    class _MockHttpResponse:
        def __init__(self, text, status=201):
            self.text = text
            self.status = status

        def read(self):
            return self.text.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=_MockHttpResponse(fake_sdp_answer, status=201)):
        res = client.post(
            f"/api/stream/{dp}/whep",
            headers={"Content-Type": "application/sdp", "X-RTMS-Token": "test_v260_secret_token_123"},
            content=fake_sdp_offer,
        )

        assert res.status_code == 201 or res.status_code == 200
        assert res.headers["content-type"].startswith("application/sdp")
        assert res.headers["access-control-allow-origin"] == "*"
        assert fake_sdp_answer in res.text

    # Limpieza
    proc.state = State.STOPPED
    proc.process = None


def test_telemetry_websocket_endpoint_unauthorized(client):
    """Valida que /ws/telemetry rechace clientes sin token o con token incorrecto."""
    with pytest.raises((WebSocketDisconnect, RuntimeError)):
        with client.websocket_connect("/ws/telemetry?token=token_falso_invalido"):
            pass


def test_telemetry_websocket_endpoint_authorized(client):
    """Valida conexión autorizada al WebSocket /ws/telemetry y respuesta ping/pong."""
    with client.websocket_connect("/ws/telemetry?token=test_v260_secret_token_123") as ws:
        ws.send_text("ping")
        # El canal puede emitir telemetría reactiva en paralelo; leemos hasta recibir pong
        received_pong = False
        for _ in range(5):
            resp = ws.receive_text()
            if resp == "pong":
                received_pong = True
                break
            msg = json.loads(resp)
            assert msg["type"] in ("telemetry", "event")
        assert received_pong is True


@pytest.mark.asyncio
async def test_telemetry_hub_broadcast_lifecycle():
    """Valida el ciclo de vida del ticker en TelemetryWebSocketHub al registrar/desregistrar."""
    hub = TelemetryWebSocketHub()
    mock_ws = AsyncMock()

    assert hub.client_count == 0
    await hub.register(mock_ws)
    assert hub.client_count == 1
    assert hub._ticker_task is not None
    assert not hub._ticker_task.done()

    # Event broadcast
    await hub.broadcast_event("test_event", {"val": 123})
    assert mock_ws.send_text.called

    await hub.unregister(mock_ws)
    assert hub.client_count == 0
    await hub.stop()


def test_snyk_workflow_configuration():
    """Valida que el workflow de Snyk exista y contenga los parámetros requeridos."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workflow_path = os.path.join(repo_root, ".github", "workflows", "snyk.yml")

    assert os.path.isfile(workflow_path), "El archivo .github/workflows/snyk.yml debe existir."

    with open(workflow_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "jobs" in data
    assert "snyk-scan" in data["jobs"] or "snyk" in data["jobs"]
    job = data["jobs"].get("snyk-scan") or data["jobs"].get("snyk")
    steps = job.get("steps", [])

    step_uses = [s.get("uses", "") for s in steps]
    assert any("snyk/actions/python" in u for u in step_uses)
    assert any("upload-sarif" in u for u in step_uses)


@pytest.mark.asyncio
async def test_command_builder_mjpeg_silicon_fallback_when_unsupported_or_failed():
    """Valida que no se inyecte -vcodec mjpeg cuando el dispositivo no lo soporta o falló."""
    # 1. Cuando mjpeg_supported es False
    proc_no_mjpeg = StreamProc("@device_no_mjpeg")
    proc_no_mjpeg.mjpeg_supported = False
    cmd1, _, _ = await build_ffmpeg_command(
        {
            "friendly_name": "Integrated Laptop Webcam",
            "device_path": "@device_no_mjpeg",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "is_virtual": False,
        },
        proc=proc_no_mjpeg,
    )
    assert "-vcodec" not in cmd1

    # 2. Cuando mjpeg_input_failed es True
    proc_failed = StreamProc("@device_failed")
    proc_failed.mjpeg_input_failed = True
    cmd2, _, _ = await build_ffmpeg_command(
        {
            "friendly_name": "USB Webcam",
            "device_path": "@device_failed",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "is_virtual": False,
        },
        proc=proc_failed,
    )
    assert "-vcodec" not in cmd2


@pytest.mark.asyncio
async def test_probe_device_mjpeg_support():
    """Valida la función probe_device_mjpeg_support para dispositivos virtuales y físicos."""
    from core.hardware import _mjpeg_support_cache, probe_device_mjpeg_support

    _mjpeg_support_cache.clear()

    # Virtual device siempre retorna False sin llamar a subprocess
    assert await probe_device_mjpeg_support("virtual://test") is False
    assert await probe_device_mjpeg_support("testsrc") is False

    # Con mock de salida DirectShow que tiene pixel_format=mjpeg
    with patch("core.hardware.has_ffmpeg_binary", return_value=True), patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Pin Capturar: pixel_format=mjpeg fps=30")
        mock_exec.return_value = mock_proc

        result = await probe_device_mjpeg_support("@test_usb_cam_mjpeg")
        assert result is True

    # Con mock de salida DirectShow que NO tiene mjpeg (solo yuyv/nv12)
    with patch("core.hardware.has_ffmpeg_binary", return_value=True), patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Pin Capturar: pixel_format=yuyv422 fps=30")
        mock_exec.return_value = mock_proc

        result = await probe_device_mjpeg_support("@test_usb_cam_yuyv")
        assert result is False


@pytest.mark.asyncio
async def test_stream_manager_mjpeg_fallback_recovery():
    """Valida que _collect_logs dispare _fallback_from_mjpeg ante rechazo de opciones en DirectShow."""
    from core.stream_manager import StreamManager

    sm = StreamManager()
    proc = sm.get_proc("@device_options_rejected")
    proc.state = State.RUNNING
    proc.mjpeg_supported = True
    proc.mjpeg_input_failed = False

    mock_process = AsyncMock()

    # Generar línea de error de DirectShow
    async def mock_stderr_gen():
        yield b"[in#0] Could not set video options\n"
        yield b"Error opening input: I/O error\n"

    mock_process.stderr = mock_stderr_gen()
    mock_process.wait = AsyncMock()

    with patch.object(sm, "_fallback_from_mjpeg", new_callable=AsyncMock) as mock_fallback:
        await sm._collect_logs("@device_options_rejected", mock_process)
        assert proc.mjpeg_input_failed is True
        assert proc.mjpeg_supported is False
        mock_fallback.assert_called_once_with("@device_options_rejected")
