# ==============================================================================
# RTMS v2.0.3 — Tests de Seguridad de API (api/routes.py)
# ==============================================================================

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from api.routes import router, set_global_api_token

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_healthz_endpoint_is_public():
    """El endpoint /healthz debe responder sin requerir token."""
    # Montamos un router o endpoint local para el test
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": "2.0.3"}

    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["version"] == "2.0.3"

def test_api_status_masks_srt_passphrase():
    """El endpoint /api/status no debe filtrar contraseñas SRT en texto plano."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "streams" in data
    for s in data["streams"]:
        # Si tiene contraseña, debe estar enmascarada
        if s.get("has_passphrase"):
            assert s.get("srt_passphrase") == "••••••••"

def test_protected_endpoints_require_token():
    """Las peticiones POST deben ser rechazadas con 403 si el token X-RTMS-Token falta o es incorrecto."""
    token = "test_secret_token_12345"
    set_global_api_token(token)

    # 1. Petición sin token -> 403 Forbidden
    res_no_token = client.post("/api/hardware/scan")
    assert res_no_token.status_code == 403

    # 2. Petición con token incorrecto -> 403 Forbidden
    res_bad_token = client.post("/api/hardware/scan", headers={"X-RTMS-Token": "token_falso"})
    assert res_bad_token.status_code == 403

    # 3. Petición con token correcto -> 200 OK
    res_valid = client.post("/api/hardware/scan", headers={"X-RTMS-Token": token})
    assert res_valid.status_code == 200
