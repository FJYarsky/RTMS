# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de funciones de seguridad, tickets y control.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import logging
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import create_app
from core.sanitizer import SecretFilter
from core.system_env import get_platform_details
from core.config_mgr import (
    remove_camera_config,
    unignore_device,
    is_device_ignored,
    get_or_allocate_camera_config,
)
from api.routes import preview_ticket_mgr
from core.process_cleanup import terminate_all_processes

@pytest.fixture
def client():
    app = create_app(token="test_audit_secret_token_123")
    return TestClient(app)

def test_secret_filter_with_format_args():
    """Valida que SecretFilter maneje correctamente records de logging con args %s sin TypeError (Claude N2)."""
    filter_instance = SecretFilter()
    logger = logging.getLogger("test.secret.filter")
    logger.setLevel(logging.INFO)

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Usuario %s intento conectar con clave %s",
        args=("admin", "passphrase=MiClaveSecreta123"),
        exc_info=None
    )

    # Debe ejecutarse sin lanzar TypeError
    res = filter_instance.filter(record)
    assert res is True
    assert "MiClaveSecreta123" not in record.msg
    assert "********" in record.msg
    assert record.args == ()

def test_preview_ticket_single_use_and_invalidation():
    """Valida consumo único estricto (single-use) e invalidación por dispositivo (Claude N7, N8 / ChatGPT P0-01, P1-03)."""
    dp = "@device_camera_test_ticket"
    ticket = preview_ticket_mgr.create_ticket(dp, ttl=60)
    assert ticket is not None

    # Primer consumo debe ser exitoso
    assert preview_ticket_mgr.consume_ticket(ticket, dp) is True

    # Segundo consumo con el mismo ticket debe fallar (replay attack prevention)
    assert preview_ticket_mgr.consume_ticket(ticket, dp) is False

    # Crear otro ticket e invalidar por dispositivo
    ticket2 = preview_ticket_mgr.create_ticket(dp, ttl=60)
    preview_ticket_mgr.invalidate_for_device(dp)
    assert preview_ticket_mgr.consume_ticket(ticket2, dp) is False

def test_preview_ticket_capacity_limit():
    """Valida que el gestor de tickets no crezca indefinidamente (cap a 100) (Claude N8 / ChatGPT P1-02)."""
    for i in range(150):
        preview_ticket_mgr.create_ticket(f"@cam_{i}", ttl=1)
    assert len(preview_ticket_mgr._tickets) <= 100

def test_get_platform_details_returns_valid_structure():
    """Valida que get_platform_details() retorne estructura esperada para el HUD y página de sistema (U-9)."""
    info = get_platform_details()
    assert isinstance(info, dict)
    assert "os" in info
    assert "architecture" in info
    assert "summary" in info
    assert "Windows" in info["summary"]

def test_ignored_devices_persists_on_camera_delete():
    """Valida que al eliminar una cámara se agregue a ignored_devices para evitar que el hotplug la resucite (Claude N1)."""
    test_dp = "@device_ignored_camera_test"

    cam_cfg = get_or_allocate_camera_config(test_dp, "Cam Ignored Test")
    cam_id = cam_cfg["id"]

    # Verificar que inicialmente no está ignorada
    assert not is_device_ignored(test_dp)

    # Eliminar cámara
    success = remove_camera_config(cam_id)
    assert success is True

    # Debe estar ahora en ignored_devices
    assert is_device_ignored(test_dp) is True

    # Des-ignorar
    unignore_device(test_dp)
    assert is_device_ignored(test_dp) is False

def test_factory_reset_endpoint_requires_confirmation(client):
    """Valida que el endpoint de restablecimiento de fábrica exija confirmación explícita (U-5)."""
    res = client.post(
        "/api/system/factory_reset",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"},
        json={"confirm": False}
    )
    assert res.status_code == 400

def test_factory_reset_endpoint_success(client):
    """Valida que el endpoint de restablecimiento limpie archivos de configuración y logs (U-5)."""
    with patch("main.terminate_all_processes"):
        with patch("threading.Thread"):
            res = client.post(
                "/api/system/factory_reset",
                headers={"X-RTMS-Token": "test_audit_secret_token_123"},
                json={"confirm": True}
            )
            assert res.status_code == 200
            assert res.json()["status"] == "ok"

def test_system_shutdown_endpoint(client):
    """Valida que el endpoint de shutdown invoque la terminación ordenada de procesos (U-3)."""
    with patch("threading.Thread") as mock_thread:
        res = client.post(
            "/api/system/shutdown",
            headers={"X-RTMS-Token": "test_audit_secret_token_123"},
            json={"force": True}
        )
        assert res.status_code == 200
        assert mock_thread.called

def test_process_cleanup_terminate_all():
    """Valida que terminate_all_processes intente detener streams y cerrar recursos."""
    with patch("core.single_instance.release_single_instance_lock") as mock_release:
        with patch("os._exit") as mock_exit:
            with patch("core.ffmpeg_mgr.stream_manager.stop_all"):
                with patch("core.preview_mgr.preview_manager.stop_all"):
                    terminate_all_processes(force=False)
                    assert mock_release.called
                    assert mock_exit.called

def test_connect_url_endpoint_requires_auth(client):
    """Valida que el endpoint connect_url exija autenticación por token."""
    res = client.get("/api/stream/@nonexistent_device/connect_url")
    assert res.status_code == 403

def test_connect_url_endpoint_not_found(client):
    """Valida que el endpoint retorne 404 para dispositivos no registrados."""
    res = client.get(
        "/api/stream/@nonexistent_device/connect_url",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"}
    )
    assert res.status_code == 404

def test_connect_url_endpoint_srt_and_udp(client):
    """Valida generación de URL de conexión para OBS/vMix en protocolos SRT y UDP."""
    # 1. Cámara SRT con passphrase
    srt_cam = get_or_allocate_camera_config("@device_srt_connect_test", "SRT Connect Test")
    srt_dp = srt_cam["device_path"]
    from core.config_mgr import update_camera_config
    update_camera_config(srt_dp, "720p", 30, 3000, protocol="srt", srt_passphrase="MySecretPassphrase123")

    res = client.get(
        f"/api/stream/{srt_dp}/connect_url",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "srt"
    assert data["has_passphrase"] is True
    assert "srt://" in data["connect_url"]
    assert "mode=caller" in data["connect_url"]
    assert "passphrase=MySecretPassphrase123" in data["connect_url"]

    # 2. Cámara UDP
    udp_cam = get_or_allocate_camera_config("@device_udp_connect_test", "UDP Connect Test")
    udp_dp = udp_cam["device_path"]
    update_camera_config(udp_dp, "720p", 30, 3000, protocol="udp")

    res_udp = client.get(
        f"/api/stream/{udp_dp}/connect_url",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"}
    )
    assert res_udp.status_code == 200
    data_udp = res_udp.json()
    assert data_udp["status"] == "ok"
    assert data_udp["protocol"] == "udp"
    assert "udp://239.255.0." in data_udp["connect_url"]

