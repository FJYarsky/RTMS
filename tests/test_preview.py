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

def test_preview_endpoint_accepts_query_token(client):
    # With query param token -> should not be 403 (e.g. 200 or streaming)
    with patch.object(preview_manager, "has_ffmpeg_binary", return_value=True):
        with patch.object(preview_manager, "generate_mjpeg_stream") as mock_gen:
            async def dummy_gen(*args, **kwargs):
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfakejpg\r\n"
            mock_gen.return_value = dummy_gen()

            res = client.get("/api/stream/test_cam/preview?token=test_preview_secret_token_123")
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
    with patch.object(preview_manager, "launch_ffplay", return_value=True):
        res = client.post(
            "/api/stream/test_cam/ffplay",
            headers={"X-RTMS-Token": "test_preview_secret_token_123"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
