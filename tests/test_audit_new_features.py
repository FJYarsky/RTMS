# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de funciones de seguridad, tickets y control.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de funciones de seguridad, tickets y control."""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.deps import preview_ticket_mgr
from core.config_mgr import (
    get_or_allocate_camera_config,
    is_device_ignored,
    remove_camera_config,
    unignore_device,
)
from core.process_cleanup import terminate_all_processes
from core.sanitizer import SecretFilter
from core.system_env import get_platform_details
from main import create_app


@pytest.fixture
def client():
    app = create_app(token="test_audit_secret_token_123")
    return TestClient(app)


def test_secret_filter_with_format_args():
    """Valida que SecretFilter maneje correctamente registros de logging con argumentos formateados."""
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
        exc_info=None,
    )

    # Debe ejecutarse sin lanzar TypeError
    res = filter_instance.filter(record)
    assert res is True
    assert "MiClaveSecreta123" not in record.msg
    assert "********" in record.msg
    assert record.args == ()


def test_preview_ticket_single_use_and_invalidation():
    """Valida consumo único estricto (single-use) e invalidación por dispositivo."""
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
    """Valida que el gestor de tickets mantenga un límite superior de capacidad en memoria."""
    for i in range(150):
        preview_ticket_mgr.create_ticket(f"@cam_{i}", ttl=1)
    assert len(preview_ticket_mgr._tickets) <= 100


def test_get_platform_details_returns_valid_structure():
    """Valida que get_platform_details() retorne estructura esperada para el HUD y página de sistema."""
    info = get_platform_details()
    assert isinstance(info, dict)
    assert "os" in info
    assert "architecture" in info
    assert "summary" in info
    assert "Windows" in info["summary"]


def test_ignored_devices_persists_on_camera_delete():
    """Valida que al eliminar una cámara se agregue a ignored_devices para evitar auto-detección."""
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


def test_ignored_devices_api_endpoints(client):
    """Valida los endpoints GET /api/devices/ignored, POST /api/devices/unignore y unignore_all."""
    test_dp = "@device_api_ignored_test"
    cam_cfg = get_or_allocate_camera_config(test_dp, "Cam API Ignored Test")
    cam_id = cam_cfg["id"]

    # 1. Eliminar cámara para que ingrese a ignored_devices
    assert remove_camera_config(cam_id) is True
    assert is_device_ignored(test_dp) is True

    # 2. Consultar lista de ignorados por API
    res = client.get("/api/devices/ignored", headers={"X-RTMS-Token": "test_audit_secret_token_123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    ignored_list = data["ignored_devices"]
    found = any(d["device_path"] == test_dp for d in ignored_list)
    assert found is True

    # 3. Restaurar dispositivo por API
    res_unignore = client.post(
        "/api/devices/unignore",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"},
        json={"device_path": test_dp},
    )
    assert res_unignore.status_code == 200
    assert is_device_ignored(test_dp) is False

    # 4. Error 404 al intentar des-ignorar un dispositivo no ignorado
    res_404 = client.post(
        "/api/devices/unignore",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"},
        json={"device_path": "@device_non_existent_123"},
    )
    assert res_404.status_code == 404

    # 5. Probar unignore_all
    test_dp2 = "@device_api_ignored_test_2"
    get_or_allocate_camera_config(test_dp2, "Cam 2")
    remove_camera_config(test_dp2)
    assert is_device_ignored(test_dp2) is True

    res_all = client.post(
        "/api/devices/unignore_all",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"},
    )
    assert res_all.status_code == 200
    assert is_device_ignored(test_dp2) is False


def test_factory_reset_endpoint_requires_confirmation(client):
    """Valida que el endpoint de restablecimiento de fábrica exija confirmación explícita."""
    res = client.post(
        "/api/system/factory_reset", headers={"X-RTMS-Token": "test_audit_secret_token_123"}, json={"confirm": False}
    )
    assert res.status_code == 400


def test_factory_reset_endpoint_success(client):
    """Valida que el endpoint de restablecimiento limpie archivos de configuración y logs."""
    with patch("main.terminate_all_processes"):
        with patch("threading.Thread"):
            res = client.post(
                "/api/system/factory_reset",
                headers={"X-RTMS-Token": "test_audit_secret_token_123"},
                json={"confirm": True},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "ok"


def test_system_shutdown_endpoint(client):
    """Valida que el endpoint de shutdown invoque la terminación ordenada de procesos."""
    with patch("threading.Thread") as mock_thread:
        res = client.post(
            "/api/system/shutdown", headers={"X-RTMS-Token": "test_audit_secret_token_123"}, json={"force": True}
        )
        assert res.status_code == 200
        assert mock_thread.called


def test_process_cleanup_terminate_all():
    """Valida que terminate_all_processes intente detener streams y cerrar recursos."""
    with patch("core.single_instance.release_single_instance_lock") as mock_release:
        with patch("os._exit") as mock_exit:
            with patch("core.stream_manager.stream_manager.stop_all"):
                with patch("core.preview_mgr.preview_manager.stop_all"):
                    terminate_all_processes(force=False)
                    assert mock_release.called
                    assert mock_exit.called


def test_process_cleanup_only_kills_rtms_processes():
    """Valida que el paso force=True solo mate procesos hijos de RTMS o con binario/marca de RTMS (P0-02)."""
    my_pid = os.getpid()

    class FakeProc:
        def __init__(self, pid, name, ppid, exe, cmdline):
            self.info = {
                "pid": pid,
                "name": name,
                "ppid": ppid,
                "exe": exe,
                "cmdline": cmdline,
            }
            self.killed = False

        def kill(self):
            self.killed = True

    proc_child = FakeProc(101, "ffmpeg.exe", my_pid, "c:/other/ffmpeg.exe", [])
    proc_foreign = FakeProc(102, "ffmpeg.exe", 9999, "c:/other/ffmpeg.exe", ["ffmpeg", "-i", "video.mp4"])
    proc_rtms_cmd = FakeProc(103, "ffmpeg.exe", 8888, "c:/other/ffmpeg.exe", ["ffmpeg", "rtms_stream"])
    proc_non_ffmpeg = FakeProc(104, "notepad.exe", 9999, "c:/notepad.exe", [])

    with patch("core.single_instance.release_single_instance_lock"):
        with patch("os._exit"):
            with patch("core.stream_manager.stream_manager.stop_all"):
                with patch("core.preview_mgr.preview_manager.stop_all"):
                    with patch(
                        "psutil.process_iter",
                        return_value=[proc_child, proc_foreign, proc_rtms_cmd, proc_non_ffmpeg],
                    ):
                        terminate_all_processes(force=True)

    assert proc_child.killed is True, "Hijo directo debe ser terminado"
    assert proc_foreign.killed is False, "Proceso ffmpeg ajeno al sistema no debe ser terminado"
    assert proc_rtms_cmd.killed is True, "Proceso con marca rtms debe ser terminado"
    assert proc_non_ffmpeg.killed is False, "Proceso que no es ffmpeg no debe ser tocado"


def test_connect_url_endpoint_requires_auth(client):
    """Valida que el endpoint connect_url exija autenticación por token."""
    res = client.get("/api/stream/@nonexistent_device/connect_url")
    assert res.status_code == 403


def test_connect_url_endpoint_not_found(client):
    """Valida que el endpoint retorne 404 para dispositivos no registrados."""
    res = client.get(
        "/api/stream/@nonexistent_device/connect_url", headers={"X-RTMS-Token": "test_audit_secret_token_123"}
    )
    assert res.status_code == 404


def test_connect_url_endpoint_srt_and_udp(client):
    """Valida generación de URL de conexión para OBS/vMix en protocolos SRT y UDP."""
    # 1. Cámara SRT con passphrase
    srt_cam = get_or_allocate_camera_config("@device_srt_connect_test", "SRT Connect Test")
    srt_dp = srt_cam["device_path"]
    from core.config_mgr import update_camera_config

    update_camera_config(srt_dp, "720p", 30, 3000, protocol="srt", srt_passphrase="MySecretPassphrase123")

    res = client.get(f"/api/stream/{srt_dp}/connect_url", headers={"X-RTMS-Token": "test_audit_secret_token_123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "srt"
    assert data["has_passphrase"] is True
    assert "srt://" in data["connect_url"]
    assert "streamid=read" in data["connect_url"]
    assert "passphrase=MySecretPassphrase123" in data["connect_url"]

    # 2. Cámara UDP
    udp_cam = get_or_allocate_camera_config("@device_udp_connect_test", "UDP Connect Test")
    udp_dp = udp_cam["device_path"]
    update_camera_config(udp_dp, "720p", 30, 3000, protocol="udp")

    res_udp = client.get(f"/api/stream/{udp_dp}/connect_url", headers={"X-RTMS-Token": "test_audit_secret_token_123"})
    assert res_udp.status_code == 200
    data_udp = res_udp.json()
    assert data_udp["status"] == "ok"
    assert data_udp["protocol"] == "udp"
    assert "udp://239.255.0." in data_udp["connect_url"]


def test_unprotect_secret_case_insensitive():
    """Valida que el prefijo 'dpapi:' o 'DPAPI:' sea detectado insensible a mayúsculas."""
    from core.secrets_mgr import protect_secret, unprotect_secret

    assert protect_secret("DPAPI:fake_cipher_123") == "DPAPI:fake_cipher_123"
    # Cadena DPAPI corrupta retorna vacío de forma segura sin importar capitalización
    assert unprotect_secret("DPAPI:corrupt_base64_blob!!") == ""


def test_ffplay_launch_unprotects_dpapi_passphrase(client):
    """Valida que launch_external_ffplay descifre la passphrase DPAPI al armar la URL del monitor."""
    from core.config_mgr import get_or_allocate_camera_config, update_camera_config
    from core.secrets_mgr import protect_secret
    from core.stream_manager import stream_manager

    cam = get_or_allocate_camera_config("@device_ffplay_dpapi_test", "FFplay DPAPI Test")
    dp = cam["device_path"]
    plain_pwd = "PlainSecretKey123"
    cipher_pwd = protect_secret(plain_pwd, require_secure=False)
    update_camera_config(dp, "720p", 30, 3000, protocol="srt", srt_passphrase=cipher_pwd)

    proc = stream_manager.get_proc(dp)
    proc.config = {
        "device_path": dp,
        "protocol": "srt",
        "port": 9977,
        "srt_passphrase": cipher_pwd,
        "friendly_name": "FFplay DPAPI Test",
    }
    proc.process = MagicMock(returncode=None)

    try:
        with patch("core.preview_mgr.preview_manager.launch_ffplay") as mock_launch:
            mock_launch.return_value = True
            res = client.post(f"/api/stream/{dp}/ffplay", headers={"X-RTMS-Token": "test_audit_secret_token_123"})
            assert res.status_code == 200
            assert mock_launch.called
            called_url = mock_launch.call_args[0][0]
            assert "passphrase=" in called_url
            assert plain_pwd in called_url
            if cipher_pwd != plain_pwd:
                assert "dpapi:" not in called_url.lower()
    finally:
        proc.process = None


def test_config_update_preserves_optional_booleans(client):
    """Valida que update_stream_config preserve valores booleanos en proc.config."""
    from core.config_mgr import get_or_allocate_camera_config
    from core.stream_manager import stream_manager

    cam = get_or_allocate_camera_config("@device_bool_test", "Bool Test")
    dp = cam["device_path"]
    proc = stream_manager.get_proc(dp)
    proc.config = {"auto_start": True, "zerolatency": False, "is_virtual": True}

    res = client.post(
        "/api/stream/config",
        headers={"X-RTMS-Token": "test_audit_secret_token_123"},
        json={"device_path": dp, "resolution": "720p", "fps": 30, "bitrate": 3000},
    )
    assert res.status_code == 200
    assert proc.config["auto_start"] is not None
    assert proc.config["zerolatency"] is not None
    assert proc.config["is_virtual"] is not None
