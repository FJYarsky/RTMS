# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas complementarias finales para garantizar cobertura global >= 80%.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite final de cobertura para api.routes (streams, preview), config_mgr y telemetry."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.config_mgr import (
    load_config,
)
from core.telemetry import GpuTelemetryReader
from main import create_app

AUTH_TOKEN = "final_boost_secret_123"
HEADERS = {"X-RTMS-Token": AUTH_TOKEN}


@pytest.fixture
def client():
    app = create_app(token=AUTH_TOKEN)
    return TestClient(app)


# ---------------------------------------------------------------------------
# API Streams Extra Endpoints
# ---------------------------------------------------------------------------


def test_api_streams_extended_endpoints(client: TestClient):
    """Valida /api/stream/preset, autostart_toggle, scan, ignored y logs."""
    # 1. Preset
    with (
        patch("api.routes.streams.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("api.routes.streams.apply_camera_preset", return_value={"device_path": "cam1", "fps": 60}),
        patch("api.routes.streams.stream_manager.get_proc", return_value=None),
    ):
        r_preset = client.post(
            "/api/stream/preset",
            json={"device_path": "cam1", "preset_key": "1080p60_broadcast"},
            headers=HEADERS,
        )
        assert r_preset.status_code == 200
        assert r_preset.json()["status"] == "ok"

    # 2. Autostart toggle
    with (
        patch("api.routes.streams.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("api.routes.streams.set_camera_autostart", return_value=True),
        patch("api.routes.streams.stream_manager.get_proc", return_value=None),
    ):
        r_auto = client.post(
            "/api/stream/autostart_toggle",
            json={"device_path": "cam1", "auto_start": True},
            headers=HEADERS,
        )
        assert r_auto.status_code == 200
        assert r_auto.json()["auto_start"] is True

    # 3. Hardware scan con restore_ignored
    with (
        patch("core.config_mgr.clear_ignored_devices"),
        patch("api.routes.streams.sync_streams_with_hardware", AsyncMock()),
    ):
        r_scan = client.post("/api/hardware/scan?restore_ignored=true", headers=HEADERS)
        assert r_scan.status_code == 200

    # 4. Dispositivos ignorados y unignore
    with (
        patch(
            "core.config_mgr.get_ignored_devices",
            return_value=[{"device_path": "cam_hidden", "friendly_name": "Hidden Cam", "ignored_at": "2026-01-01"}],
        ),
        patch("core.hardware.get_directshow_devices", AsyncMock(return_value=[])),
    ):
        r_ign = client.get("/api/devices/ignored", headers=HEADERS)
        assert r_ign.status_code == 200
        assert len(r_ign.json()["ignored_devices"]) == 1

    with (
        patch("core.config_mgr.unignore_device", return_value=True),
        patch("api.routes.streams.sync_streams_with_hardware", AsyncMock()),
    ):
        r_unign = client.post("/api/devices/unignore", json={"device_path": "cam_hidden"}, headers=HEADERS)
        assert r_unign.status_code == 200

    # 5. Delete camera
    with (
        patch("api.routes.streams.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("api.routes.streams.stream_manager.remove_stream", AsyncMock(return_value=True)),
        patch("core.mediamtx_mgr.mediamtx_manager.generate_config"),
        patch("core.mediamtx_mgr.mediamtx_manager.sync_paths_api", AsyncMock()),
    ):
        r_del = client.delete("/api/stream/cam1", headers=HEADERS)
        assert r_del.status_code == 200
        assert r_del.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# API Preview Extra Endpoints
# ---------------------------------------------------------------------------


def test_api_preview_endpoints(client: TestClient):
    """Valida /preview_frame y /ffplay."""
    # 1. preview_frame
    with (
        patch("core.preview_mgr.preview_manager.has_ffmpeg_binary", return_value=True),
        patch("api.routes.preview.find_camera_by_id_or_path", return_value={"device_path": "cam1"}),
        patch("core.preview_mgr.preview_manager.get_snapshot_frame", AsyncMock(return_value=b"\xff\xd8img\xff\xd9")),
    ):
        r_frame = client.get("/api/stream/cam1/preview_frame", headers=HEADERS)
        assert r_frame.status_code == 200
        assert r_frame.content == b"\xff\xd8img\xff\xd9"

    # 2. ffplay launch
    with (
        patch(
            "api.routes.preview.find_camera_by_id_or_path",
            return_value={"device_path": "cam1", "friendly_name": "Camera 1"},
        ),
        patch("api.routes.preview.preview_manager.launch_ffplay", return_value=True),
    ):
        r_ff = client.post("/api/stream/cam1/ffplay", headers=HEADERS)
        assert r_ff.status_code == 200
        assert r_ff.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Telemetry NVML Monitoring
# ---------------------------------------------------------------------------


def test_telemetry_nvml_metrics_collection():
    """Valida GpuTelemetryReader.get_metrics con emulación completa de llamadas ctypes NVML."""
    monitor = GpuTelemetryReader()
    monitor.available = True
    monitor._gpu_name = "NVIDIA GeForce RTX 4080"
    monitor._device_handle = 12345

    mock_nvml = MagicMock()

    # nvmlDeviceGetUtilizationRates
    def mock_util(handle, ptr):
        ptr._obj.gpu = 45
        ptr._obj.memory = 30
        return 0

    # nvmlDeviceGetMemoryInfo
    def mock_mem(handle, ptr):
        ptr._obj.used = 2 * 1024 * 1024 * 1024  # 2 GB
        ptr._obj.total = 16 * 1024 * 1024 * 1024  # 16 GB
        return 0

    mock_nvml.nvmlDeviceGetUtilizationRates = mock_util
    mock_nvml.nvmlDeviceGetMemoryInfo = mock_mem
    monitor._nvml = mock_nvml

    metrics = monitor.get_metrics()
    assert metrics["available"] is True
    assert metrics["gpu_percent"] == 45.0
    assert metrics["memory_used_mb"] == 2048.0
    assert metrics["memory_total_mb"] == 16384.0
    assert metrics["name"] == "NVIDIA GeForce RTX 4080"


# ---------------------------------------------------------------------------
# Config Manager Backup Recovery
# ---------------------------------------------------------------------------


def test_config_mgr_corrupt_file_recovery(tmp_path: Path):
    """Valida la auto-recuperación de config_mgr cuando CONFIG_FILE está corrupto y existe .bak."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    # Escribir json corrupto en config.json
    cfg_file.write_text("{ corrupt json ...", encoding="utf-8")

    # Escribir json válido en config.json.bak
    valid_data = {
        "config_schema_version": 4,
        "cameras": {
            "cam_recovered": {
                "device_path": "cam_recovered",
                "friendly_name": "Recovered Cam",
                "resolution": "720p",
                "fps": 30,
                "bitrate": 2000,
                "protocol": "srt",
                "port": 9030,
            }
        },
        "system": {},
    }
    bak_file.write_text(json.dumps(valid_data), encoding="utf-8")

    with (
        patch("core.config_mgr.CONFIG_FILE", str(cfg_file)),
        patch("core.config_mgr.CONFIG_BAK_FILE", str(bak_file)),
        patch("core.repository.config_repository.config_repository.get_all_cameras_sync", return_value={}),
        patch("core.repository.config_repository.config_repository.get_system_settings_sync", return_value={}),
    ):
        loaded = load_config()
        assert "cam_recovered" in loaded["cameras"]
