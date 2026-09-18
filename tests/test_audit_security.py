# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de seguridad, cifrado DPAPI y protección de datos.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import sys
import time
import logging
import pytest
from fastapi.testclient import TestClient
from core.secrets_mgr import unprotect_secret, SecretDecryptionError
from core.sanitizer import SecretFilter, sanitize_url
from api.routes import preview_ticket_mgr
from main import create_app
from core.config_mgr import save_config

@pytest.mark.skipif(sys.platform != "win32", reason="Requiere DPAPI de Windows")
def test_unprotect_secret_failure_never_leaks_ciphertext(monkeypatch):
    """Verifica que unprotect_secret retorne cadena vacía o lance SecretDecryptionError ante fallos, sin filtrar nunca el texto cifrado."""
    import base64
    fake_ciphertext = "dpapi:" + base64.b64encode(b"DummyCiphertextPayload").decode("utf-8")

    # Simulate CryptUnprotectData failure returning 0
    monkeypatch.setattr("ctypes.windll.crypt32.CryptUnprotectData", lambda *args: 0)

    # 1. Default safe mode returns empty string, NOT ciphertext
    result = unprotect_secret(fake_ciphertext, raise_on_error=False)
    assert result == "", "Failed unprotect_secret must return empty string, never ciphertext"

    # 2. raise_on_error=True raises SecretDecryptionError
    with pytest.raises(SecretDecryptionError):
        unprotect_secret(fake_ciphertext, raise_on_error=True)

def test_secret_filter_and_sanitize_url():
    """Verifica que SecretFilter y sanitize_url enmascaren contraseñas y parámetros sensibles en URLs y logs."""
    # 1. Test sanitize_url
    srt_url = "srt://127.0.0.1:9000?mode=caller&passphrase=SuperSecretPassword123&latency=120000"
    sanitized = sanitize_url(srt_url)
    assert "SuperSecretPassword123" not in sanitized
    assert "passphrase=********" in sanitized or "••••••••" in sanitized

    # 2. Test SecretFilter in logging
    sfilter = SecretFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Connecting to srt://192.168.1.50:9000?passphrase=MySecretPassword with token secret_token_abc",
        args=(),
        exc_info=None
    )
    sfilter.filter(record)
    assert "MySecretPassword" not in record.msg
    assert "********" in record.msg

def test_config_export_security():
    """Verifica la exportación segura de configuración y el requerimiento de confirmación explícita para secretos en texto plano."""
    token = "test_token_secret_123"
    app = create_app(token=token)
    client = TestClient(app)

    # Seed config with camera having passphrase
    cfg = {
        "version": "2.2.2",
        "cameras": {
            "cam1": {
                "friendly_name": "Stage Camera",
                "device_path": "video=StageCam",
                "srt_passphrase": "RealSecretPassphrase123",
                "port": 9000
            }
        }
    }
    save_config(cfg)

    headers = {"X-RTMS-Token": token}

    # GET export always masks secrets (safe_mode=True forced)
    get_res = client.get("/api/config/export", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["cameras"]["cam1"]["srt_passphrase"] == "••••••••"
    assert data["cameras"]["cam1"]["has_passphrase"] is True

    # POST full export without confirmation returns HTTP 400
    post_unconfirmed = client.post(
        "/api/config/export/full",
        headers=headers,
        json={"confirm_export_secrets": False}
    )
    assert post_unconfirmed.status_code == 400

    # POST full export with confirmation returns plaintext secrets
    post_confirmed = client.post(
        "/api/config/export/full",
        headers=headers,
        json={"confirm_export_secrets": True}
    )
    assert post_confirmed.status_code == 200
    data_full = post_confirmed.json()
    assert data_full["cameras"]["cam1"]["srt_passphrase"] == "RealSecretPassphrase123"

def test_preview_ticket_lifecycle():
    """Verifica el ciclo de vida, validación, expiración y control de discrepancia de cámara en PreviewTicketManager."""
    dp1 = "video=CamOne"
    dp2 = "video=CamTwo"

    # 1. Create ticket with short TTL (1 sec)
    ticket = preview_ticket_mgr.create_ticket(dp1, ttl=1)
    assert ticket is not None
    assert len(ticket) >= 32

    # 2. Validation with matching camera succeeds
    assert preview_ticket_mgr.validate_ticket(ticket, dp1) is True

    # 3. Validation with mismatched camera fails
    assert preview_ticket_mgr.validate_ticket(ticket, dp2) is False

    # 4. Wait for expiration (1.1 sec)
    time.sleep(1.1)
    assert preview_ticket_mgr.validate_ticket(ticket, dp1) is False, "Expired ticket must be invalid"
