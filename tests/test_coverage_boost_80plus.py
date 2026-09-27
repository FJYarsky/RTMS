# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas adicionales para superar holgadamente el umbral del 80% de cobertura.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas complementarias para alcanzar y superar el 80% de cobertura de código."""

import asyncio
import io
import urllib.error
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ffmpeg_tester import FFmpegDiagnosticSuite
from core.mediamtx_mgr import MediaMTXManager
from core.power_mgr import (
    apply_network_power_settings,
    get_net_adapters_pnp,
)
from core.preview_mgr import PreviewManager
from core.stream_manager import StreamManager
from core.stream_proc import ErrorCategory, State

# ---------------------------------------------------------------------------
# PreviewManager Deep Coverage
# ---------------------------------------------------------------------------


def test_preview_mgr_launch_ffplay_all_modes():
    """Valida launch_ffplay con virtual, dshow, network, urls inválidas y reemplazo de instancias activas."""
    pm = PreviewManager()

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("core.preview_mgr.get_ffplay_bin", return_value="ffplay.exe"),
        patch("core.preview_mgr.os.path.exists", return_value=True),
        patch("subprocess.Popen") as mock_popen,
    ):
        mock_proc1 = MagicMock()
        mock_proc1.poll.return_value = None
        mock_popen.return_value = mock_proc1

        # 1. Virtual
        assert pm.launch_ffplay("virtual://test", title="Virtual Test", is_virtual=True) is True

        # 2. DirectShow
        mock_proc2 = MagicMock()
        mock_proc2.poll.return_value = None
        mock_popen.return_value = mock_proc2
        assert pm.launch_ffplay("Integrated Camera", title="Cam Test", is_dshow=True) is True

        # 3. DirectShow inválido
        assert pm.launch_ffplay("-invalid_arg", is_dshow=True) is False

        # 4. Network SRT
        assert pm.launch_ffplay("srt://127.0.0.1:8890?streamid=read:cam1", title="SRT Stream") is True

        # 5. Network Protocolo no permitido
        assert pm.launch_ffplay("ftp://127.0.0.1/video.mp4") is False

        # 6. Re-lanzar para la misma URL cierra la previa
        mock_proc3 = MagicMock()
        mock_proc3.poll.return_value = None
        mock_popen.return_value = mock_proc3
        assert pm.launch_ffplay("srt://127.0.0.1:8890?streamid=read:cam1", title="SRT Stream Replaced") is True
        assert mock_proc2.terminate.called or mock_proc1.terminate.called

        pm.terminate_all_ffplay()


@pytest.mark.asyncio
async def test_preview_mgr_snapshot_frame_all_cases():
    """Valida get_snapshot_frame con virtual, dshow y timeout."""
    pm = PreviewManager()

    with patch("core.preview_mgr.has_ffmpeg_binary", return_value=True):
        # 1. Éxito virtual
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"\xff\xd8fakejpg\xff\xd9", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            res_virt = await pm.get_snapshot_frame("virtual://testsrc2")
            assert res_virt == b"\xff\xd8fakejpg\xff\xd9"

            # 2. Éxito dshow
            res_dshow = await pm.get_snapshot_frame("Integrated Camera")
            assert res_dshow == b"\xff\xd8fakejpg\xff\xd9"

        # 3. Timeout
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with patch("asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)):
                res_to = await pm.get_snapshot_frame("Integrated Camera")
                assert res_to is None
                assert mock_proc.kill.called


@pytest.mark.asyncio
async def test_preview_mgr_generate_mjpeg_stream_data():
    """Valida canalización y corte de generate_mjpeg_stream con frames reales simulados."""
    pm = PreviewManager()

    jpeg_chunk = b"\xff\xd8fakejpegdata\xff\xd9"

    class AsyncStreamMock:
        def __init__(self):
            self._sent = False

        async def read(self, n):
            if not self._sent:
                self._sent = True
                return jpeg_chunk
            return b""

    mock_proc = MagicMock()
    mock_proc.stdout = AsyncStreamMock()
    mock_proc.wait = AsyncMock(return_value=0)

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)),
    ):
        gen = pm.generate_mjpeg_stream("srt://127.0.0.1:8890?streamid=read:cam1", identifier="test_mjpeg_1")
        frames = []
        async for chunk in gen:
            frames.append(chunk)

        assert len(frames) == 1
        assert b"--frame" in frames[0]
        assert b"image/jpeg" in frames[0]
        assert b"fakejpegdata" in frames[0]


# ---------------------------------------------------------------------------
# StreamManager Deep Coverage (Logs and Watchdog)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_manager_collect_logs_parsing():
    """Valida el análisis de telemetría y detección de patrones de error en _collect_logs."""
    sm = StreamManager()
    proc = sm.ensure_proc("cam_log_test")
    proc.state = State.RUNNING
    proc.config = {"device_path": "cam_log_test", "port": 9000}

    stderr_lines = [
        b"frame=  150 fps= 29.98 q=-1.0 size=N/A time=00:00:05.00 bitrate= 2500.5kbits/s speed= 1.0x\n",
        b"[dshow @ 000001] could not find video device with requested options\n",
        b"[error] error while opening encoder for output stream\n",
        b"[out#0/srt @ 000002] connection to srt://127.0.0.1:8890 failed: Connection refused\n",
    ]

    class AsyncLinesMock:
        def __init__(self, lines):
            self.lines = list(lines)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.lines:
                raise StopAsyncIteration
            return self.lines.pop(0)

    mock_process = MagicMock()
    mock_process.stderr = AsyncLinesMock(stderr_lines)
    mock_process.wait = AsyncMock(return_value=0)

    with (
        patch.object(sm, "_fallback_from_mjpeg", AsyncMock()),
        patch.object(sm, "_fallback_to_cpu", AsyncMock()),
        patch.object(sm, "reallocate_if_collided", AsyncMock()),
    ):
        await sm._collect_logs("cam_log_test", mock_process)

        # Telemetría parseada
        assert proc.current_fps == 29.98
        assert proc.current_bitrate_kbps == 2500.5
        assert proc.current_speed == "1.0x"
        assert proc.last_error_category in (ErrorCategory.NETWORK, ErrorCategory.ENCODER, ErrorCategory.DEVICE)


@pytest.mark.asyncio
async def test_stream_manager_watchdog_step():
    """Valida la supervisión y recuperación de flujos en State.ERROR dentro del bucle de watchdog."""
    sm = StreamManager()
    proc = sm.ensure_proc("cam_watchdog_test")
    proc.state = State.ERROR
    proc.is_connected = True
    proc.error_count = 1
    proc.next_retry_at = datetime.now() - timedelta(seconds=1)

    with (
        patch(
            "core.stream_manager.get_directshow_devices", AsyncMock(return_value=[{"device_path": "cam_watchdog_test"}])
        ),
        patch.object(sm, "start_stream", AsyncMock()),
    ):
        # Ejecutar un ciclo cancelable de watchdog
        task = asyncio.create_task(sm.watchdog())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# MediaMTXManager Deep Coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mediamtx_mgr_wait_for_api_and_supervise():
    """Valida _wait_for_api_ready y _supervise_loop."""
    mgr = MediaMTXManager()

    # 1. _wait_for_api_ready responde 200
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value.status = 200
    with patch("core.mediamtx_mgr.urllib.request.urlopen", return_value=mock_resp):
        ok = await mgr._wait_for_api_ready(timeout=0.2)
        assert ok is True

    # 2. _wait_for_api_ready agota timeout
    with patch("core.mediamtx_mgr.urllib.request.urlopen", side_effect=Exception("Connection refused")):
        ok_fail = await mgr._wait_for_api_ready(timeout=0.1)
        assert ok_fail is False

    # 3. _apply_path_api_sync manejo de error 400 con PATCH
    err_400 = urllib.error.HTTPError("url", 400, "Bad Request", {}, io.BytesIO(b"{}"))
    with patch("core.mediamtx_mgr.urllib.request.urlopen", side_effect=err_400):
        mgr._apply_path_api_sync("cam_patch", "new_secret")


# ---------------------------------------------------------------------------
# PowerManager Registry Mocks Coverage
# ---------------------------------------------------------------------------


def test_power_mgr_registry_network_adapters():
    """Valida get_net_adapters_pnp y apply_network_power_settings con mocks de winreg."""
    with patch("core.power_mgr.sys.platform", "win32"):
        mock_key = MagicMock()

        def mock_enum(key, idx):
            if idx == 0:
                return "0001"
            raise OSError("No more items")

        def mock_query(subkey, name):
            if name == "NetCfgInstanceId":
                return ("{GUID-1234}", 1)
            if name == "PnPCapabilities":
                return (24, 4)
            raise FileNotFoundError()

        with (
            patch("core.power_mgr.is_admin", return_value=True),
            patch("winreg.OpenKey", return_value=mock_key),
            patch("winreg.EnumKey", side_effect=mock_enum),
            patch("winreg.QueryValueEx", side_effect=mock_query),
            patch("winreg.SetValueEx") as mock_set,
        ):
            mock_key.__enter__.return_value = mock_key
            adapters = get_net_adapters_pnp()
            assert "0001" in adapters
            assert adapters["0001"] == 24

            updated = apply_network_power_settings()
            assert updated is True
            assert mock_set.called


# ---------------------------------------------------------------------------
# FFmpegStreamTester Deep Coverage
# ---------------------------------------------------------------------------


def test_ffmpeg_tester_probe_caps():
    """Valida probe_dshow_camera_caps con salida representativa de FFmpeg."""
    tester = FFmpegDiagnosticSuite()

    sample_dshow_output = (
        "[dshow @ 000001] DirectShow video device options (input #0)\n"
        "[dshow @ 000001]   pixel_format=mjpeg  min s=640x480 fps=30 max s=1920x1080 fps=60\n"
        "[dshow @ 000001]   pixel_format=yuyv422  min s=640x480 fps=30 max s=1280x720 fps=30\n"
    )

    mock_res = MagicMock()
    mock_res.stderr = sample_dshow_output
    mock_res.returncode = 0

    with patch("subprocess.run", return_value=mock_res):
        caps = tester.probe_dshow_camera_caps("Integrated Camera")
        assert caps["max_resolution"] == "1920x1080"
        assert caps["max_fps"] == 60.0
        assert caps["supports_1080p60"] is True
        assert len(caps["supported_modes"]) == 2


@pytest.mark.asyncio
async def test_ffmpeg_tester_benchmark_encoders():
    """Valida benchmark_encoder para libx264 y h264_nvenc."""
    tester = FFmpegDiagnosticSuite()

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b"frame=  180 fps=125.4 q=28.0 size=N/A time=00:00:03.00"))

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
        bench_cpu = await tester.benchmark_encoder("libx264", "720p", fps=30, frames=60)
        assert "encoder" in bench_cpu or "fps" in bench_cpu

        bench_nvenc = await tester.benchmark_encoder("h264_nvenc", "1080p", fps=60, frames=180)
        assert bench_nvenc is not None
