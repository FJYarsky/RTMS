# ==============================================================================
# RTMS v2.2.0 — Tests de Seguridad e Integración de API (api/routes.py & main.py)
# ==============================================================================

from fastapi.testclient import TestClient
from main import create_app

TEST_TOKEN = "test_crypto_session_token_123456789"
app = create_app(token=TEST_TOKEN)
client = TestClient(app)

def test_healthz_endpoint_is_public():
    """El endpoint /healthz debe responder 200 OK sin requerir token de sesión."""
    res = client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_sensitive_get_endpoints_require_token():
    """Valida que todos los endpoints GET sensibles rechacen peticiones sin token con 403."""
    endpoints = [
        "/api/status",
        "/api/system/metrics",
        "/api/stream/logs?device_path=dummy",
        "/api/power/status",
        "/api/config/export"
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 403, f"Endpoint {ep} no fue bloqueado sin token"

def test_sensitive_get_endpoints_with_valid_token():
    """Valida que las peticiones GET con token válido sean aceptadas."""
    headers = {"X-RTMS-Token": TEST_TOKEN}
    res_status = client.get("/api/status", headers=headers)
    assert res_status.status_code == 200

    res_metrics = client.get("/api/system/metrics", headers=headers)
    assert res_metrics.status_code == 200

    res_power = client.get("/api/power/status", headers=headers)
    assert res_power.status_code == 200

def test_api_status_masks_passphrase():
    """Valida que /api/status nunca devuelva contraseñas SRT en texto plano."""
    headers = {"X-RTMS-Token": TEST_TOKEN}
    res = client.get("/api/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "streams" in data
    for s in data["streams"]:
        if s.get("has_passphrase"):
            assert s.get("srt_passphrase") == "••••••••"

def test_mutating_post_endpoints_require_token():
    """Valida que peticiones POST sean rechazadas con 403 si falta el token o es incorrecto."""
    # Sin token
    res_no_token = client.post("/api/hardware/scan")
    assert res_no_token.status_code == 403

    # Con token erróneo
    res_bad_token = client.post("/api/hardware/scan", headers={"X-RTMS-Token": "token_falso"})
    assert res_bad_token.status_code == 403

    # Con token correcto
    res_valid = client.post("/api/hardware/scan", headers={"X-RTMS-Token": TEST_TOKEN})
    assert res_valid.status_code == 200
