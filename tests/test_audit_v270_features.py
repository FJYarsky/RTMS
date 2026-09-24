# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas de validación y regresión para versión 2.7.0.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias y de integración para las características de RTMS v2.7.0."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from api.schemas import CameraConfigUpdate, CameraPersistedConfig
from core.config_models import CameraConfig
from core.job_object import JobObjectManager
from core.mediamtx_mgr import MediaMTXManager
from core.power_mgr import DynamicPowerGovernor
from core.repository.config_repository import ConfigRepository
from core.repository.database import CURRENT_DB_SCHEMA_VERSION, get_sync_connection, run_migrations
from core.stream_manager import StreamManager
from core.stream_proc import build_client_urls
from main import app


def test_injective_multicast_port_mapping():
    """Valida que la fórmula inyectiva de mapeo multicast (p - 9000) + 1 no tenga colisiones."""
    allocated_ips = set()
    for port in range(9000, 9201):
        urls = build_client_urls("udp", "192.168.1.50", port, f"cam_{port}", udp_mode="multicast")
        vlc_url = urls["vlc_url"]
        assert "udp://@239.255.0." in vlc_url
        ip_tail = int(vlc_url.split("239.255.0.")[1].split(":")[0])
        assert ip_tail == (port - 9000) + 1
        assert ip_tail not in allocated_ips
        allocated_ips.add(ip_tail)
    assert len(allocated_ips) == 201


def test_client_urls_latency_and_unicast():
    """Valida el formato de URL para SRT cliente (sin latency= para evitar buffer bloat en VLC) y UDP Unicast (udp://@:<port>)."""
    # SRT
    srt_urls = build_client_urls("srt", "192.168.1.50", 9000, "cam_main")
    assert "srt://192.168.1.50:8890" in srt_urls["connect_url"]
    assert "streamid=read:cam_main" in srt_urls["connect_url"]
    assert "latency=" not in srt_urls["vlc_url"]

    # UDP Unicast
    udp_urls = build_client_urls("udp", "192.168.1.50", 9005, "cam_udp", udp_mode="unicast")
    assert udp_urls["vlc_url"] == "udp://@:9005"


def test_sqlite_v2_migration_and_persistence(tmp_path: Path):
    """Valida la migración incremental a esquema v2 y la persistencia de is_virtual, udp_mode y udp_host."""
    db_file = tmp_path / "test_v2.db"

    # 1. Crear base con esquema v1 antiguo (sin is_virtual, udp_mode, udp_host)
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
    )
    conn.execute("INSERT INTO schema_migrations (version) VALUES (1);")
    conn.execute(
        """
        CREATE TABLE cameras (
            device_path TEXT PRIMARY KEY,
            id TEXT,
            friendly_name TEXT NOT NULL,
            resolution TEXT NOT NULL,
            fps INTEGER NOT NULL,
            bitrate INTEGER NOT NULL,
            encoder TEXT NOT NULL,
            port INTEGER NOT NULL,
            protocol TEXT NOT NULL,
            srt_latency INTEGER NOT NULL,
            srt_passphrase TEXT,
            auto_start BOOLEAN NOT NULL DEFAULT 0,
            zerolatency BOOLEAN NOT NULL DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()

    # 2. Ejecutar run_migrations y verificar incremento a v2
    conn = get_sync_connection(str(db_file))
    run_migrations(conn)
    cur = conn.cursor()
    cur.execute("SELECT MAX(version) FROM schema_migrations;")
    ver = cur.fetchone()[0]
    assert ver == CURRENT_DB_SCHEMA_VERSION == 2

    # Verificar que las nuevas columnas existen
    cur.execute("PRAGMA table_info(cameras);")
    cols = [row[1] for row in cur.fetchall()]
    assert "is_virtual" in cols
    assert "udp_mode" in cols
    assert "udp_host" in cols
    conn.close()

    # 3. Guardar y recuperar configuración completa con el repositorio
    repo = ConfigRepository(db_path=str(db_file))
    cam = CameraPersistedConfig(
        device_path="test_device_1",
        friendly_name="Camara Prueba v2.7.0",
        resolution="1080p",
        fps=60,
        bitrate=4500,
        protocol="udp",
        udp_mode="unicast",
        udp_host="192.168.1.100",
        port=9010,
        encoder="auto",
        srt_latency=120,
        is_virtual=True,
    )
    repo.save_camera_sync("test_device_1", cam.model_dump())

    loaded = repo.get_all_cameras_sync()
    assert "test_device_1" in loaded
    l_cam = loaded["test_device_1"]
    assert bool(l_cam["is_virtual"]) is True
    assert l_cam["udp_mode"] == "unicast"
    assert l_cam["udp_host"] == "192.168.1.100"
    assert l_cam["fps"] == 60


def test_camera_config_update_patch_semantics():
    """Valida la semántica PATCH de CameraConfigUpdate donde solo los campos definidos se actualizan."""
    # Instancia con solo fps definido
    update = CameraConfigUpdate(device_path="cam_1", fps=45)
    dumped = update.model_dump(exclude_unset=True)
    assert dumped == {"device_path": "cam_1", "fps": 45}
    assert "resolution" not in dumped
    assert "bitrate" not in dumped
    assert "protocol" not in dumped

    # Configuración de base
    base_cfg = CameraConfig(
        device_path="cam_1",
        friendly_name="Cam 1",
        resolution="720p",
        fps=30,
        bitrate=2500,
        protocol="srt",
        port=9000,
    )

    merged = base_cfg.model_copy(update=dumped)
    assert merged.fps == 45
    assert merged.resolution == "720p"
    assert merged.bitrate == 2500


def test_whep_query_token_forbidden():
    """Valida que el endpoint proxy WHEP rechace tokens en query string con HTTP 403."""
    client = TestClient(app)
    res = client.post(
        "/api/stream/test_cam/whep?token=some_token",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert res.status_code == 403
    assert "deshabilitado por seguridad" in res.json()["detail"]


def test_security_csp_headers_present():
    """Valida que las respuestas HTTP incluyan cabeceras Content-Security-Policy y de blindaje."""
    client = TestClient(app)
    res = client.get("/")
    assert "content-security-policy" in res.headers
    csp = res.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self' ws: wss:" in csp
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "SAMEORIGIN"


def test_stream_manager_non_mutating_get_proc():
    """Valida que get_proc sea no-mutante y retorne None para rutas no existentes."""
    mgr = StreamManager()
    assert mgr.get_proc("non_existent_camera_123") is None
    assert len(mgr._procs) == 0

    proc = mgr.ensure_proc("existing_camera_123")
    assert proc is not None
    assert mgr.get_proc("existing_camera_123") is proc
    assert len(mgr._procs) == 1


def test_job_object_close_handle_on_opened_handle():
    """Valida que JobObjectManager cierre el handle de proceso abierto con OpenProcess."""
    mgr = JobObjectManager()
    if not mgr.is_active():
        pytest.skip("Win32 Job Object no activo en este entorno")

    fake_h_proc = 12345
    with (
        patch("ctypes.windll.kernel32.OpenProcess", return_value=fake_h_proc),
        patch("ctypes.windll.kernel32.AssignProcessToJobObject", return_value=1),
        patch("ctypes.windll.kernel32.CloseHandle") as mock_close,
    ):
        success = mgr.assign_process(99999)
        assert success is True
        mock_close.assert_called_once_with(fake_h_proc)


def test_dynamic_power_governor_stream_lifecycle():
    """Valida el comportamiento de DynamicPowerGovernor al iniciar y detener transmisiones."""
    gov = DynamicPowerGovernor()
    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.acquire_stay_awake") as mock_acquire,
        patch("core.power_mgr.release_stay_awake") as mock_release,
        patch("core.power_mgr.get_active_scheme_guid", return_value="381b4222-f694-41f0-9685-ff5bb260df2e"),
        patch("core.power_mgr.set_active_scheme", return_value=True) as mock_set_scheme,
    ):
        gov.on_stream_started(1)
        assert mock_acquire.called
        assert mock_set_scheme.called
        assert gov._is_boosted is True

        gov.on_stream_stopped(0)
        assert mock_release.called
        assert gov._is_boosted is False


def test_mediamtx_log_redirection(tmp_path: Path):
    """Valida que MediaMTX configure la redirección de logs hacia un archivo seguro."""
    mgr = MediaMTXManager(base_dir=str(tmp_path))
    assert mgr.log_path == str(tmp_path / "config" / "mediamtx.log")
