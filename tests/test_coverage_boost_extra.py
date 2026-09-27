# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas adicionales para maximizar la cobertura del sistema (>= 80%).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias extensivas para core y API para alcanzar cobertura >= 80%."""

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.mediamtx_mgr import MediaMTXManager
from core.power_mgr import (
    DynamicPowerGovernor,
    get_active_scheme_guid,
    is_admin,
    set_active_scheme,
    setup_windows_environment,
)
from core.preview_mgr import PreviewManager
from core.stream_manager import StreamManager
from core.stream_proc import ErrorCategory, State, StreamProc
from main import create_app

AUTH_TOKEN = "boost_secret_token_abc123"
HEADERS = {"X-RTMS-Token": AUTH_TOKEN}


@pytest.fixture
def client():
    app = create_app(token=AUTH_TOKEN)
    return TestClient(app)


# ---------------------------------------------------------------------------
# StreamManager Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_manager_basic_helpers():
    """Valida métodos utilitarios de StreamManager: get_proc, ensure_proc, detect_best_encoder."""
    sm = StreamManager()
    assert sm.get_proc("cam1") is None
    proc = sm.ensure_proc("cam1")
    assert proc is not None
    assert sm.get_proc("cam1") is proc

    # detect_best_encoder con encoder ya definido en proc
    proc.per_stream_encoder = "hevc_nvenc"
    enc = await sm.detect_best_encoder(proc)
    assert enc == "hevc_nvenc"

    # detect_best_encoder delegando a hardware_detector
    with patch("core.stream_manager.hardware_detector.get_best_encoder", AsyncMock(return_value="h264_qsv")):
        proc2 = StreamProc("cam2")
        enc2 = await sm.detect_best_encoder(proc2)
        assert enc2 == "h264_qsv"
        assert proc2.per_stream_encoder == "h264_qsv"


@pytest.mark.asyncio
async def test_stream_manager_start_stream_edge_cases():
    """Valida los casos borde de start_stream: ya vivo, desconectado, binario faltante, descifrado fallido."""
    sm = StreamManager()
    proc = sm.ensure_proc("test_cam")

    # 1. Ya vivo
    proc.state = State.RUNNING
    mock_sub = MagicMock()
    mock_sub.poll.return_value = None
    mock_sub.returncode = None
    proc.process = mock_sub
    assert proc.is_alive is True
    await sm.start_stream("test_cam")
    assert proc.state == State.RUNNING

    # 2. Desconectado (dispositivo físico no encontrado en DirectShow)
    proc.process = None
    proc.state = State.STOPPED
    proc.is_connected = False
    proc.config = {"is_virtual": False, "device_path": "phys_cam_not_found"}
    with (
        patch("core.config_mgr.is_virtual_device", return_value=False),
        patch("core.stream_manager.get_directshow_devices", AsyncMock(return_value=[])),
    ):
        await sm.start_stream("test_cam")
        assert proc.state == State.DISCONNECTED

    # 3. Binario FFmpeg no disponible
    proc.is_connected = True
    proc.state = State.STOPPED
    with patch("core.stream_manager.has_ffmpeg_binary", return_value=False):
        await sm.start_stream("test_cam")
        assert proc.state == State.ERROR

    # 4. Fallo de descifrado DPAPI
    proc.config["decryption_failed"] = True
    with patch("core.stream_manager.has_ffmpeg_binary", return_value=True):
        await sm.start_stream("test_cam")
        assert proc.state == State.MANUAL_INTERVENTION_REQUIRED
        assert proc.last_error_category == ErrorCategory.AUTHENTICATION


@pytest.mark.asyncio
async def test_stream_manager_start_and_stop_lifecycle():
    """Valida el ciclo de inicio y detención exitosa con mocks asíncronos."""
    sm = StreamManager()
    proc = sm.ensure_proc("virtual_cam_1")
    proc.is_connected = True
    proc.config = {
        "device_path": "virtual://testsrc2",
        "is_virtual": True,
        "resolution": "720p",
        "fps": 30,
        "bitrate": 2000,
        "protocol": "srt",
        "port": 9050,
        "encoder": "libx264",
    }

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.returncode = None
    mock_proc.pid = 99999
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.stdout = None
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.readline = AsyncMock(return_value=b"")

    with (
        patch("core.stream_manager.has_ffmpeg_binary", return_value=True),
        patch("core.stream_manager.port_manager.revalidate_port", return_value=True),
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)),
        patch("core.stream_manager.build_ffmpeg_command", AsyncMock(return_value=(["ffmpeg"], "srt://url", "libx264"))),
    ):
        await sm.start_stream("virtual_cam_1")
        assert proc.state == State.RUNNING
        assert proc.is_alive is True

        # Detener stream
        await sm.stop_stream("virtual_cam_1")
        assert proc.state == State.STOPPED


@pytest.mark.asyncio
async def test_stream_manager_restart_and_emergency_stop():
    """Valida restart_stream, stop_all y emergency_stop_all."""
    sm = StreamManager()
    sm.ensure_proc("cam_1")
    sm.ensure_proc("cam_2")

    with (
        patch.object(sm, "_start_stream_locked", AsyncMock()) as mock_start,
        patch.object(sm, "stop_stream", AsyncMock()) as mock_stop,
    ):
        await sm.restart_stream("cam_1")
        assert mock_start.called

        await sm.stop_all()
        assert mock_stop.call_count >= 2

        await sm.emergency_stop_all()
        assert mock_stop.call_count >= 4


@pytest.mark.asyncio
async def test_stream_manager_cpu_fallback_and_mjpeg_fallback():
    """Valida _fallback_to_cpu y _fallback_from_mjpeg."""
    sm = StreamManager()
    proc = sm.ensure_proc("cam_fallback")
    proc.config = {"device_path": "cam_fallback"}

    with (
        patch.object(sm, "_stop_stream_locked", AsyncMock()),
        patch.object(sm, "_start_stream_locked", AsyncMock()),
    ):
        await sm._fallback_to_cpu("cam_fallback")
        assert proc.using_fallback_cpu is True
        assert proc.per_stream_encoder == "libx264"

        await sm._fallback_from_mjpeg("cam_fallback")
        assert proc.mjpeg_input_failed is True
        assert proc.mjpeg_supported is False


# ---------------------------------------------------------------------------
# MediaMTXManager Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mediamtx_mgr_lifecycle():
    """Valida inicio, supervisión y detención de MediaMTXManager."""
    mgr = MediaMTXManager()

    # 1. Ya corriendo
    with patch.object(mgr, "is_running", return_value=True):
        assert await mgr.start() is True

    # 2. Binario no disponible
    with (
        patch.object(mgr, "is_running", return_value=False),
        patch.object(mgr, "is_binary_available", return_value=False),
    ):
        assert await mgr.start() is False

    # 3. Flujo exitoso de inicio
    mock_sub = MagicMock()
    mock_sub.poll.return_value = None

    with (
        patch.object(mgr, "is_running", return_value=False),
        patch.object(mgr, "is_binary_available", return_value=True),
        patch.object(mgr, "generate_config", return_value="dummy_path.yml"),
        patch.object(mgr, "get_bin_path", return_value="dummy_mediamtx.exe"),
        patch("subprocess.Popen", return_value=mock_sub),
        patch.object(mgr, "_wait_for_api_ready", AsyncMock(return_value=True)),
        patch.object(mgr, "sync_paths_api", AsyncMock(return_value=True)),
    ):
        ok = await mgr.start(srt_port=8890)
        assert ok is True
        assert mgr._process is mock_sub

        # Detención
        mgr.stop()
        assert mgr._process is None
        assert mock_sub.terminate.called


@pytest.mark.asyncio
async def test_mediamtx_mgr_sync_and_paths():
    """Valida get_paths, sync_path_api y _apply_path_api_sync."""
    mgr = MediaMTXManager()

    # get_paths cuando no está corriendo
    with patch.object(mgr, "is_running", return_value=False):
        assert await mgr.get_paths() == []

    # get_paths cuando está corriendo
    with patch.object(mgr, "is_running", return_value=True):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value.status = 200
        mock_resp.__enter__.return_value.read.return_value = b'{"items": [{"name": "cam1"}]}'
        with patch("core.mediamtx_mgr.urllib.request.urlopen", return_value=mock_resp):
            paths = await mgr.get_paths()
            assert len(paths) == 1
            assert paths[0]["name"] == "cam1"

    # _apply_path_api_sync para agregar y eliminar
    mock_ok = MagicMock()
    mock_ok.__enter__.return_value.status = 200
    with patch("core.mediamtx_mgr.urllib.request.urlopen", return_value=mock_ok):
        mgr._apply_path_api_sync("cam_test", "secret_pass")
        mgr._apply_path_api_sync("cam_test", "")


# ---------------------------------------------------------------------------
# PowerManager Tests
# ---------------------------------------------------------------------------


def test_power_mgr_is_admin():
    """Valida detección de permisos administrativos en Windows y no-Windows."""
    with patch("core.power_mgr.sys.platform", "linux"):
        assert is_admin() is False

    with patch("core.power_mgr.sys.platform", "win32"):
        mock_ctypes = MagicMock()
        mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            assert is_admin() is True


def test_power_mgr_scheme_and_governor():
    """Valida manipulación de planes de energía y DynamicPowerGovernor."""
    with patch("core.power_mgr.sys.platform", "win32"):
        # get_active_scheme_guid vía fallback powercfg
        mock_sub = MagicMock()
        mock_sub.stdout = "GUID de combinación de energía: 381b4222-f694-41f0-9685-ff5bb260df2e  (Equilibrado)"
        mock_sub.returncode = 0
        with (
            patch("ctypes.windll.powrprof.PowerGetActiveScheme", return_value=1),
            patch("core.power_mgr.subprocess.run", return_value=mock_sub),
        ):
            guid = get_active_scheme_guid()
            assert guid == "381b4222-f694-41f0-9685-ff5bb260df2e"

        # set_active_scheme
        with patch("core.power_mgr.subprocess.run", return_value=MagicMock(returncode=0)):
            assert set_active_scheme("381b4222-f694-41f0-9685-ff5bb260df2e") is True

        # DynamicPowerGovernor
        gov = DynamicPowerGovernor()
        with (
            patch("core.power_mgr.acquire_stay_awake", return_value=True),
            patch("core.power_mgr.release_stay_awake", return_value=True),
            patch("core.power_mgr.get_active_scheme_guid", return_value="381b4222-f694-41f0-9685-ff5bb260df2e"),
            patch("core.power_mgr.set_active_scheme", return_value=True),
        ):
            gov.on_stream_started(1)
            assert gov._is_boosted is True
            assert gov._lock_held is True

            gov.on_stream_stopped(0)
            assert gov._is_boosted is False
            assert gov._lock_held is False

            # shutdown
            gov.shutdown()


def test_power_mgr_setup_windows_environment():
    """Valida setup_windows_environment en modo administrador y no administrador."""
    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.is_admin", return_value=True),
        patch("core.power_mgr.backup_current_power_settings", return_value=True),
        patch("core.power_mgr.get_active_scheme_guid", return_value="381b4222-f694-41f0-9685-ff5bb260df2e"),
        patch("core.power_mgr.set_active_scheme", return_value=True),
        patch("core.power_mgr.apply_network_power_settings", return_value=True),
        patch("core.power_mgr.subprocess.run", return_value=MagicMock(returncode=0)),
    ):
        res = setup_windows_environment()
        assert res["status"] in ("ok", "partial")
        assert len(res["applied"]) > 0

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.is_admin", return_value=False),
        patch("core.power_mgr.backup_current_power_settings", return_value=True),
        patch("core.power_mgr.get_active_scheme_guid", return_value="381b4222-f694-41f0-9685-ff5bb260df2e"),
        patch("core.power_mgr.subprocess.run", return_value=MagicMock(returncode=0)),
    ):
        res_non_admin = setup_windows_environment()
        assert any("requiere permisos de Administrador" in w for w in res_non_admin["warnings"])


# ---------------------------------------------------------------------------
# API Route Tests (Config and Streams)
# ---------------------------------------------------------------------------


def test_api_config_export_and_import(client: TestClient):
    """Valida GET /api/config/export, POST /api/config/export/full y POST /api/config/import."""
    # 1. Exportación simple
    r_exp = client.get("/api/config/export", headers=HEADERS)
    assert r_exp.status_code == 200
    assert "cameras" in r_exp.json()

    # 2. Exportación completa sin confirmación (debe fallar con 400)
    r_full_fail = client.post("/api/config/export/full", json={"confirm_export_secrets": False}, headers=HEADERS)
    assert r_full_fail.status_code == 400

    # 3. Exportación completa con confirmación
    r_full_ok = client.post("/api/config/export/full", json={"confirm_export_secrets": True}, headers=HEADERS)
    assert r_full_ok.status_code == 200

    # 4. Importación con carga inválida
    r_imp_fail = client.post("/api/config/import", json={"config_data": {"invalid": "shape"}}, headers=HEADERS)
    assert r_imp_fail.status_code in (400, 422)

    # 5. Importación válida con reinicio selectivo
    valid_cfg = {
        "config_schema_version": 4,
        "cameras": {
            "test_cam_imp": {
                "device_path": "test_cam_imp",
                "friendly_name": "Imported Cam",
                "resolution": "720p",
                "fps": 30,
                "bitrate": 2500,
                "protocol": "srt",
                "port": 9015,
                "is_virtual": True,
            }
        },
        "system": {},
    }
    with patch("api.routes.config.sync_streams_with_hardware", AsyncMock()):
        r_imp_ok = client.post("/api/config/import", json={"config_data": valid_cfg}, headers=HEADERS)
        assert r_imp_ok.status_code == 200
        assert r_imp_ok.json()["status"] == "ok"


def test_api_streams_control_routes(client: TestClient):
    """Valida los endpoints de control de flujo en /api/status y /api/stream/action."""
    # GET /api/status
    r_status = client.get("/api/status", headers=HEADERS)
    assert r_status.status_code == 200
    assert "streams" in r_status.json()

    # POST /api/stream/action: stop
    with patch("api.routes.streams.stream_manager.stop_stream", AsyncMock()):
        r_stop = client.post(
            "/api/stream/action",
            json={"action": "stop", "device_path": "cam1"},
            headers=HEADERS,
        )
        assert r_stop.status_code == 200
        assert r_stop.json()["status"] == "ok"

    # POST /api/stream/action: start (cuando la cámara existe en config)
    with (
        patch("api.routes.streams.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("api.routes.streams.stream_manager.start_stream", AsyncMock()),
    ):
        r_start = client.post(
            "/api/stream/action",
            json={"action": "start", "device_path": "cam1"},
            headers=HEADERS,
        )
        assert r_start.status_code == 200
        assert r_start.json()["status"] == "ok"

    # POST /api/stream/action: restart
    with (
        patch("api.routes.streams.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("api.routes.streams.stream_manager.restart_stream", AsyncMock()),
    ):
        r_restart = client.post(
            "/api/stream/action",
            json={"action": "restart", "device_path": "cam1"},
            headers=HEADERS,
        )
        assert r_restart.status_code == 200
        assert r_restart.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# PreviewManager Concurrency and Snapshot Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_manager_concurrency_slots():
    """Valida el límite de slots de concurrencia de PreviewManager."""
    pm = PreviewManager()
    assert await pm.acquire_slot("slot_1") is True
    assert await pm.acquire_slot("slot_1") is False  # Misma cámara rechazada

    assert await pm.acquire_slot("slot_2") is True
    assert await pm.acquire_slot("slot_3") is True
    # Cuarto slot debe ser denegado por MAX_CONCURRENT_PREVIEWS = 3
    assert await pm.acquire_slot("slot_4") is False

    await pm.release_slot("slot_2")
    assert await pm.acquire_slot("slot_4") is True

    await pm.stop_all()


@pytest.mark.asyncio
async def test_preview_manager_snapshot_and_mjpeg():
    """Valida get_snapshot_frame y corte ordenado de generate_mjpeg_stream."""
    pm = PreviewManager()

    # get_snapshot_frame cuando falta binario
    with patch("core.preview_mgr.has_ffmpeg_binary", return_value=False):
        snap = await pm.get_snapshot_frame("virtual://test")
        assert snap is None

    # generate_mjpeg_stream cuando falta binario
    with patch("core.preview_mgr.has_ffmpeg_binary", return_value=False):
        gen = pm.generate_mjpeg_stream("virtual://test")
        items = [x async for x in gen]
        assert len(items) == 0


# ---------------------------------------------------------------------------
# JobObject and ProcessCleanup Tests
# ---------------------------------------------------------------------------


def test_job_object_manager_lifecycle():
    """Valida métodos de JobObjectManager: is_active, assign_process y close."""
    from core.job_object import JobObjectManager

    with (
        patch("ctypes.windll.kernel32.AssignProcessToJobObject", return_value=1),
        patch("ctypes.windll.kernel32.OpenProcess", return_value=1234),
        patch("ctypes.windll.kernel32.CloseHandle", return_value=1),
    ):
        jom = JobObjectManager()
        if jom._is_supported:
            mock_proc = MagicMock(spec=subprocess.Popen)
            mock_proc._handle = 1234
            mock_proc.pid = 9999
            assert jom.assign_process(mock_proc) is True
            assert jom.assign_process(9999) is True
            assert jom.assign_process("not_a_process") is False  # type: ignore[arg-type]
            jom.close()
            assert jom.job_handle is None
            assert jom.is_active() is False


def test_process_cleanup_terminate_all():
    """Valida terminate_all_processes con mocks controlados."""
    from core.process_cleanup import terminate_all_processes

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = False

    with (
        patch("core.process_cleanup.os._exit") as mock_exit,
        patch("asyncio.get_event_loop", return_value=mock_loop),
        patch("core.preview_mgr.preview_manager.stop_all", AsyncMock()),
        patch("core.stream_manager.stream_manager.stop_all", AsyncMock()),
        patch("core.mediamtx_mgr.mediamtx_manager.stop"),
        patch("core.telemetry.telemetry_service.shutdown"),
        patch("core.system_env.release_stay_awake"),
        patch("psutil.Process"),
        patch("psutil.wait_procs", return_value=([], [])),
    ):
        terminate_all_processes(force=False)
        assert mock_loop.run_until_complete.called
        assert mock_exit.called


# ---------------------------------------------------------------------------
# StreamManager Synchronization and Diagnostics Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_manager_sync_with_devices_and_reallocate():
    """Valida sync_with_devices y reallocate_if_collided."""
    sm = StreamManager()
    proc1 = sm.ensure_proc("cam_usb_1")
    proc1.is_connected = True
    proc1.config = {"device_path": "cam_usb_1", "friendly_name": "USB Cam 1", "port": 9000}

    # Dispositivo desconectado
    with (
        patch("core.stream_manager.get_directshow_devices", AsyncMock(return_value=[])),
        patch("core.stream_manager.mediamtx_manager.sync_paths_api", AsyncMock()),
    ):
        await sm.sync_streams_with_hardware()
        assert proc1.is_connected is False
        assert proc1.state == State.DISCONNECTED

    # Dispositivo reconectado
    fake_devs = [{"device_path": "cam_usb_1", "friendly_name": "USB Cam 1"}]
    with (
        patch("core.stream_manager.get_directshow_devices", AsyncMock(return_value=fake_devs)),
        patch("core.stream_manager.mediamtx_manager.sync_paths_api", AsyncMock()),
        patch("core.config_mgr.is_device_ignored", return_value=False),
        patch("core.config_mgr.get_or_allocate_camera_config", return_value={"port": 9000, "auto_start": False}),
    ):
        await sm.sync_streams_with_hardware()
        assert proc1.is_connected is True
        assert proc1.state == State.STOPPED

    # Reasignación de puerto ante colisión
    with (
        patch("core.stream_manager.port_manager.reallocate_if_collided", return_value=9020),
        patch("core.config_mgr.load_config", return_value={"cameras": {}}),
        patch("core.config_mgr.save_config"),
    ):
        new_p = await sm.reallocate_if_collided(proc1)
        assert new_p == 9020
        assert proc1.config["port"] == 9020
