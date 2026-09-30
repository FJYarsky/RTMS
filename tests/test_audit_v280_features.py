# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas de validación y regresión para versión 2.8.0.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias y de integración para las características de RTMS v2.8.0."""

from unittest.mock import MagicMock, patch

import pytest

from core.command_builder import build_ffmpeg_command
from core.power_mgr import BALANCED_GUID, HIGH_PERFORMANCE_GUID, DynamicPowerGovernor
from core.stream_proc import build_client_urls
from core.system_env import setup_firewall_rules


def test_v280_srt_urls_no_slash_before_query():
    """Valida que las URLs SRT generadas no contengan barra diagonal antes de '?' (libsrt / VLC Android) e incluyan parámetros de baja latencia."""
    urls = build_client_urls("srt", "192.168.1.100", 9000, "cam_test", passphrase="test_secret")
    assert "srt://192.168.1.100:8890?streamid=read:cam_test" in urls["connect_url"]
    assert "/?" not in urls["connect_url"]
    assert "/?" not in urls["vlc_url"]
    assert "passphrase=test_secret" in urls["connect_url"]
    assert "latency=50000" in urls["vlc_url"]
    assert "rcvbuf=65536" in urls["vlc_url"]
    assert "tlpktdrop=1" in urls["vlc_url"]


def test_v280_firewall_rules_covers_mediamtx_port():
    """Valida que setup_firewall_rules incluya el puerto 8890 de MediaMTX en el rango UDP."""
    with (
        patch("core.system_env.sys.platform", "win32"),
        patch("core.system_env.is_admin", return_value=True),
        patch("core.system_env.subprocess.run") as mock_run,
    ):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        res = setup_firewall_rules()
        assert res is True
        # Verificar que netsh fue llamado con regla que cubre 8890
        calls = [c[0][0] for c in mock_run.call_args_list if c[0]]
        add_rule_calls = [cmd for cmd in calls if "add" in cmd and "rule" in cmd]
        assert len(add_rule_calls) >= 1
        port_arg = [arg for arg in add_rule_calls[0] if arg.startswith("localport=")][0]
        assert "8889-8990" in port_arg


@pytest.mark.asyncio
async def test_v280_gop_and_low_delay_flags():
    """Valida que build_ffmpeg_command enforce GOP de 15 frames (500 ms a 30 fps) y banderas low_delay."""
    cfg = {
        "device_path": "video=TestCam",
        "resolution": "720p",
        "fps": 30,
        "encoder": "libx264",
        "bitrate": 3000,
        "zerolatency": True,
        "gop": 15,
        "port": 9000,
        "protocol": "srt",
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)
    assert "-g" in cmd
    gop_idx = cmd.index("-g")
    assert cmd[gop_idx + 1] == "15"
    assert "-keyint_min" in cmd
    assert cmd[cmd.index("-keyint_min") + 1] == "15"
    assert "-sc_threshold" in cmd
    assert cmd[cmd.index("-sc_threshold") + 1] == "0"
    assert "-an" in cmd
    assert "-fflags" in cmd
    assert "nobuffer" in cmd[cmd.index("-fflags") + 1]


def test_v280_power_governor_lifecycle():
    """Valida el ciclo de vida del DynamicPowerGovernor con streams concurrentes."""
    gov = DynamicPowerGovernor()
    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.get_active_scheme_guid", return_value=BALANCED_GUID),
        patch("core.power_mgr.set_active_scheme", return_value=True) as mock_set,
        patch("core.power_mgr.acquire_stay_awake", return_value=True),
        patch("core.power_mgr.release_stay_awake", return_value=True),
    ):
        # 1er stream
        gov.on_stream_started(1)
        assert gov._is_boosted is True
        mock_set.assert_called_with(HIGH_PERFORMANCE_GUID)

        # 2do stream concurrent
        mock_set.reset_mock()
        gov.on_stream_started(2)
        assert not mock_set.called

        # Parar 1 stream
        gov.on_stream_stopped(1)
        assert gov._is_boosted is True

        # Parar todos
        gov.on_stream_stopped(0)
        assert gov._is_boosted is False
        mock_set.assert_called_with(BALANCED_GUID)


@pytest.mark.asyncio
async def test_v280_mjpeg_input_usb_saving():
    """Valida que -vcodec mjpeg se inyecte antes de -i para dispositivos físicos ahorrando bus USB."""
    cfg = {
        "device_path": "HD Pro Webcam C920",
        "resolution": "1080p",
        "fps": 30,
        "encoder": "libx264",
        "bitrate": 4000,
        "zerolatency": True,
        "gop": 15,
        "port": 9000,
        "protocol": "srt",
        "use_mjpeg_input": True,
    }
    cmd, _, _ = await build_ffmpeg_command(cfg, force_cpu=True)
    assert "-vcodec" in cmd
    vcodec_idx = cmd.index("-vcodec")
    assert cmd[vcodec_idx + 1] == "mjpeg"
    assert vcodec_idx < cmd.index("-i")


def test_v280_whep_query_token_forbidden():
    """Valida que el endpoint /api/stream/{device_path}/whep rechace query token por directiva de seguridad."""
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    res = client.post(
        "/api/stream/test_cam/whep?token=unauthorized_token",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_v280_hevc_and_av1_command_tuning():
    """Valida la generación y parámetros de comando para códecs HEVC y AV1."""
    # 1. HEVC NVENC
    cfg_hevc = {
        "device_path": "virtual://test",
        "resolution": "1080p",
        "fps": 60,
        "encoder": "hevc_nvenc",
        "bitrate": 6000,
        "zerolatency": True,
        "port": 9000,
        "protocol": "srt",
    }
    cmd_hevc, _, _ = await build_ffmpeg_command(cfg_hevc)
    assert "-c:v" in cmd_hevc
    assert cmd_hevc[cmd_hevc.index("-c:v") + 1] == "hevc_nvenc"
    assert "nv12" in cmd_hevc[cmd_hevc.index("-pix_fmt") + 1]
    assert "-an" in cmd_hevc

    # 2. AV1 NVENC
    cfg_av1 = {
        "device_path": "virtual://test",
        "resolution": "1080p",
        "fps": 60,
        "encoder": "av1_nvenc",
        "bitrate": 4000,
        "zerolatency": True,
        "port": 9002,
        "protocol": "srt",
    }
    cmd_av1, _, _ = await build_ffmpeg_command(cfg_av1)
    assert "-c:v" in cmd_av1
    assert cmd_av1[cmd_av1.index("-c:v") + 1] == "av1_nvenc"

    # 3. CPU libx265
    cfg_x265 = {
        "device_path": "virtual://test",
        "resolution": "720p",
        "fps": 30,
        "encoder": "libx265",
        "bitrate": 2000,
        "zerolatency": True,
        "port": 9004,
        "protocol": "srt",
    }
    cmd_x265, _, _ = await build_ffmpeg_command(cfg_x265)
    assert "-c:v" in cmd_x265
    assert cmd_x265[cmd_x265.index("-c:v") + 1] == "libx265"


def test_v280_schemas_accept_hevc_and_av1():
    """Valida que los esquemas de API y modelos de persistencia acepten los nuevos códecs HEVC y AV1."""
    from api.schemas import CameraConfigUpdate, CameraPersistedConfig
    from core.config_models import CameraConfig

    for enc in ("hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265", "av1_nvenc", "av1_qsv", "av1_amf"):
        update = CameraConfigUpdate(device_path="test_cam", encoder=enc)  # type: ignore[arg-type]
        assert update.encoder == enc

        persisted = CameraPersistedConfig(device_path="test_cam", encoder=enc)  # type: ignore[arg-type]
        assert persisted.encoder == enc

        domain = CameraConfig(friendly_name="Cam", device_path="test_cam", encoder=enc)  # type: ignore[arg-type]
        assert domain.encoder == enc


def test_v280_prometheus_metrics_endpoint():
    """Valida que el endpoint /metrics devuelva formato plano Prometheus con métricas gauge."""
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "rtms_active_streams" in text
    assert "rtms_total_streams" in text
    assert "rtms_total_bitrate_kbps" in text
    assert "rtms_cpu_percent" in text
    assert "rtms_memory_percent" in text


def test_v280_ecs_json_formatter():
    """Valida que ECSJsonFormatter genere JSON conforme con los campos requeridos de ECS."""
    import json
    import logging

    from core.ecs_logger import ECSJsonFormatter

    formatter = ECSJsonFormatter(service_name="rtms-test")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Prueba de mensaje estructurado",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["log.level"] == "INFO"
    assert data["message"] == "Prueba de mensaje estructurado"
    assert data["service.name"] == "rtms-test"
    assert "@timestamp" in data
    assert "process.pid" in data


def test_v280_gui_modal_scroll_and_reset_button():
    """Valida soporte de scroll responsivo en CSS, botón de reset en index.html y función en app.js e i18n."""
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(base_dir, "gui", "static", "styles.css")
    html_path = os.path.join(base_dir, "gui", "templates", "index.html")
    js_path = os.path.join(base_dir, "gui", "static", "app.js")
    i18n_path = os.path.join(base_dir, "gui", "static", "i18n.js")

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    assert "max-height: calc(100vh - 40px)" in css
    assert "overflow-y: auto" in css
    assert ".modal-body" in css
    assert ".modal-foot" in css
    assert ".btn-secondary" in css

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "btn-reset-cam-defaults" in html
    assert 'data-i18n="btn_reset_cam_defaults"' in html
    assert "resetCameraConfigToDefaults()" in html

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()
    assert "function resetCameraConfigToDefaults()" in js
    assert "applyQualityPreset('default')" in js

    with open(i18n_path, "r", encoding="utf-8") as f:
        i18n = f.read()
    assert 'btn_reset_cam_defaults: "Restablecer por Defecto"' in i18n
    assert 'btn_reset_cam_defaults: "Reset to Defaults"' in i18n


def test_v280_main_window_maximized():
    """Valida que main.py configure la ventana nativa pywebview maximizada por defecto."""
    import os

    main_py_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    with open(main_py_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "maximized=True" in content


@pytest.mark.asyncio
async def test_v280_preview_reconnect_flags_and_safe_reentry():
    """Valida que preview_manager soporte auto-reemplazo seguro de slot y banderas de reconexión FFmpeg."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from core.preview_mgr import PreviewManager

    pm = PreviewManager()

    # 1. Slot re-entry seguro para la misma cámara
    assert await pm.acquire_slot("cam_stream_1") is True
    assert await pm.acquire_slot("cam_stream_1") is True  # Re-entry exitoso sin 429
    assert "cam_stream_1" in pm._active_camera_previews

    # 2. Banderas de reconexión FFmpeg en generate_mjpeg_stream
    captured_cmd = []

    async def fake_subprocess(*args, **kwargs):
        captured_cmd.extend(args)
        mock_p = MagicMock()
        mock_p.pid = 999
        mock_p.stdout = AsyncMock()
        mock_p.stdout.read = AsyncMock(return_value=b"")
        mock_p.returncode = 0
        mock_p.terminate = MagicMock()
        mock_p.wait = AsyncMock(return_value=0)
        return mock_p

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess),
    ):
        gen = pm.generate_mjpeg_stream("srt://127.0.0.1:8890?streamid=read:cam_stream_1", identifier="cam_stream_1")
        _ = [chunk async for chunk in gen]

    assert "-reconnect" in captured_cmd
    assert "-reconnect_at_eof" in captured_cmd
    assert "-reconnect_streamed" in captured_cmd
    assert "-reconnect_delay_max" in captured_cmd

    await pm.stop_all()
    assert len(pm._active_camera_previews) == 0
