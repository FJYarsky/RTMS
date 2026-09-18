# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del servicio y control de acceso a previsualizaciones.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import create_app
from core.preview_mgr import preview_manager

@pytest.fixture
def client():
    app = create_app(token="test_preview_secret_token_123")
    return TestClient(app)

def test_preview_endpoint_requires_auth(client):
    # Without token -> 403
    res = client.get("/api/stream/test_cam/preview")
    assert res.status_code == 403

def test_preview_endpoint_rejects_global_token_in_query(client):
    # Global API token in query parameter must be strictly rejected
    res = client.get("/api/stream/test_cam/preview?token=test_preview_secret_token_123")
    assert res.status_code == 403

def test_preview_endpoint_accepts_ephemeral_ticket(client):
    # Ephemeral preview ticket flow
    with patch.object(preview_manager, "has_ffmpeg_binary", return_value=True):
        with patch.object(preview_manager, "generate_mjpeg_stream") as mock_gen:
            async def dummy_gen(*args, **kwargs):
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfakejpg\r\n"
            mock_gen.return_value = dummy_gen()

            # 1. Request ticket with auth header
            t_res = client.post(
                "/api/stream/test_cam/preview_ticket",
                headers={"X-RTMS-Token": "test_preview_secret_token_123"},
                json={"ttl_seconds": 30}
            )
            assert t_res.status_code == 200
            ticket = t_res.json()["ticket"]

            # 2. Access preview with ephemeral ticket
            res = client.get(f"/api/stream/test_cam/preview?ticket={ticket}")
            assert res.status_code == 200
            assert "multipart/x-mixed-replace" in res.headers["content-type"]

def test_preview_endpoint_accepts_header_token(client):
    with patch.object(preview_manager, "has_ffmpeg_binary", return_value=True):
        with patch.object(preview_manager, "generate_mjpeg_stream") as mock_gen:
            async def dummy_gen(*args, **kwargs):
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfakejpg\r\n"
            mock_gen.return_value = dummy_gen()

            res = client.get(
                "/api/stream/test_cam/preview",
                headers={"X-RTMS-Token": "test_preview_secret_token_123"}
            )
            assert res.status_code == 200

def test_ffplay_launch_requires_auth(client):
    res = client.post("/api/stream/test_cam/ffplay")
    assert res.status_code == 403

def test_ffplay_launch_success(client):
    fake_cam = {"device_path": "test_cam", "friendly_name": "Test Camera", "port": 9000}
    with patch("api.routes.find_camera_by_id_or_path", return_value=fake_cam):
        with patch.object(preview_manager, "launch_ffplay", return_value=True):
            res = client.post(
                "/api/stream/test_cam/ffplay",
                headers={"X-RTMS-Token": "test_preview_secret_token_123"}
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"


def test_ffplay_launch_not_found(client):
    with patch("api.routes.find_camera_by_id_or_path", return_value=None):
        res = client.post(
            "/api/stream/unknown_cam/ffplay",
            headers={"X-RTMS-Token": "test_preview_secret_token_123"}
        )
        assert res.status_code == 404
