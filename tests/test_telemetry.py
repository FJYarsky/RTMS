"""Unit and integration tests for GPU and network telemetry in RTMS v2.2.0."""

# ==============================================================================
# RTMS v2.2.0 — Tests de Telemetría (tests/test_telemetry.py)
# ==============================================================================

from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from core.telemetry import GpuTelemetryReader, NetworkTelemetryTracker, SystemTelemetryService
from main import create_app

TEST_TOKEN = "telemetry_test_token_secret_12345"
app = create_app(token=TEST_TOKEN)
client = TestClient(app)


def test_network_telemetry_tracker_keys_and_values():
    """Valida que NetworkTelemetryTracker retorne la estructura y tipos esperados."""
    tracker = NetworkTelemetryTracker()
    metrics = tracker.get_metrics()

    expected_keys = ["sent_kbps", "recv_kbps", "total_kbps", "sent_mbps", "recv_mbps", "total_mbps"]
    for k in expected_keys:
        assert k in metrics
        assert isinstance(metrics[k], (int, float))
        assert metrics[k] >= 0.0


def test_network_telemetry_rollover_protection():
    """Valida que el tracker no genere valores negativos si los contadores de psutil se reinician."""
    tracker = NetworkTelemetryTracker()
    tracker._last_time = 0.0
    tracker._last_sent = 1000000
    tracker._last_recv = 1000000

    fake_io = MagicMock()
    fake_io.bytes_sent = 500  # Menor que _last_sent (reinicio de adaptador)
    fake_io.bytes_recv = 500

    with patch("psutil.net_io_counters", return_value=fake_io):
        metrics = tracker.get_metrics()
        assert metrics["sent_kbps"] >= 0.0
        assert metrics["recv_kbps"] >= 0.0
        assert metrics["total_kbps"] >= 0.0


def test_gpu_telemetry_reader_fallback_when_unavailable():
    """Valida que GpuTelemetryReader maneje la ausencia de GPU sin excepciones."""
    reader = GpuTelemetryReader()
    reader.available = False
    reader._nvml = None
    reader._device_handle = None

    stats = reader.get_metrics()
    assert stats["available"] is False
    assert stats["gpu_percent"] is None
    assert stats["name"] is None
    assert stats["memory_used_mb"] is None
    assert stats["memory_total_mb"] is None


def test_system_telemetry_service_collect():
    """Valida que SystemTelemetryService provea todas las métricas requeridas para el HUD."""
    service = SystemTelemetryService.get_instance()
    data = service.collect(active_streams_count=2, total_bitrate_kbps=4500.0)

    # Métricas base existentes
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "memory_used_mb" in data
    assert "memory_total_mb" in data
    assert data["active_streams_count"] == 2
    assert data["total_bitrate_kbps"] == 4500.0

    # Nuevas métricas GPU
    assert "gpu_available" in data
    assert isinstance(data["gpu_available"], bool)
    assert "gpu_percent" in data
    assert "gpu_name" in data

    # Nuevas métricas Red
    assert "net_sent_kbps" in data
    assert "net_recv_kbps" in data
    assert "net_total_kbps" in data
    assert isinstance(data["net_total_kbps"], (int, float))


def test_api_system_metrics_endpoint_telemetry():
    """Valida que el endpoint GET /api/system/metrics retorne la telemetría completa."""
    headers = {"X-RTMS-Token": TEST_TOKEN}
    res = client.get("/api/system/metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "gpu_available" in data
    assert "net_total_kbps" in data
    assert "active_streams_count" in data
    assert "total_bitrate_kbps" in data
