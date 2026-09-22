# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de resiliencia de streaming, MediaMTX, Job Object y SQLite WAL.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Suite de pruebas de resiliencia para la Fase 2 (v2.5.0):
- Inmunidad del pipeline ante reconexiones de clientes
- Ciclo de vida y blindaje de Windows Job Object
- Cancelación ordenada de TaskRegistry
- Configuración y puertos de MediaMTX
- Persistencia transaccional ACID con SQLite WAL y migración reversible
"""

import asyncio
import os
import subprocess
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from core.job_object import job_object_mgr
from core.mediamtx_mgr import MediaMTXManager
from core.repository import (
    ConfigRepository,
    auto_migrate_json_to_sqlite,
    export_sqlite_to_json,
    init_db,
)
from core.stream_proc import State, StreamProc
from core.task_registry import TaskRegistry
from main import create_app


@pytest.mark.asyncio
async def test_job_object_lifecycle():
    """Valida la operatividad del Job Object de Windows."""
    # En Windows debe estar activo; en otros sistemas debe degradar graciosamente
    if os.name == "nt":
        assert job_object_mgr.is_active() is True
    else:
        assert job_object_mgr.is_active() is False

    # Asignar un proceso real
    proc = subprocess.Popen(["python", "-c", "import time; time.sleep(0.5)"], stdout=subprocess.DEVNULL)
    try:
        # No debe levantar excepciones ni romper
        job_object_mgr.assign_process(proc)
    finally:
        proc.terminate()
        proc.wait()


@pytest.mark.asyncio
async def test_task_registry_lifecycle():
    """Valida la creación, registro y cancelación limpia en TaskRegistry."""
    registry = TaskRegistry()
    ran = False

    async def sample_task():
        nonlocal ran
        try:
            await asyncio.sleep(10.0)
            ran = True
        except asyncio.CancelledError:
            pass

    t = registry.create_task(sample_task(), name="test_task")
    assert t in registry.active_tasks
    assert not t.done()

    # Cancelar todas las tareas registradas
    await registry.cancel_all(timeout=1.0)
    assert t.done()
    assert len(registry.active_tasks) == 0
    assert not ran


def test_mediamtx_config_generation():
    """Valida la generación determinista de la configuración YAML de MediaMTX."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = MediaMTXManager(base_dir=tmp_dir)
        cfg_path = mgr.generate_config(srt_port=8895)
        assert os.path.exists(cfg_path)

        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "api: yes" in content
        assert "srt: yes" in content
        assert "srtAddress: :8895" in content
        assert "rtsp: no" in content
        assert "rtmp: no" in content
        assert "hls: no" in content
        assert mgr.get_srt_port() == 8895


def test_sqlite_wal_acid_persistence():
    """Valida transacciones ACID, soporte WAL y recuperación en SQLite."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_rtms.db")
        init_db(db_path)
        repo = ConfigRepository(db_path=db_path)

        # 1. Guardar cámara
        sample_cam = {
            "id": "cam_test_01",
            "friendly_name": "USB WebCam Test",
            "resolution": "1080p",
            "fps": 60,
            "bitrate": 5000,
            "encoder": "libx264",
            "port": 9050,
            "protocol": "srt",
            "srt_latency": 150,
            "srt_passphrase": "",
            "zerolatency": True,
            "auto_start": False,
        }
        repo.save_camera_sync("@device:pnp:test_01", sample_cam)

        cams = repo.get_all_cameras_sync()
        assert "@device:pnp:test_01" in cams
        assert cams["@device:pnp:test_01"]["friendly_name"] == "USB WebCam Test"
        assert cams["@device:pnp:test_01"]["port"] == 9050

        # 2. Dispositivos ignorados
        repo.add_ignored_device_sync("@device:pnp:ignored_01", "Camara Eliminada")
        assert repo.is_device_ignored_sync("@device:pnp:ignored_01") is True
        assert repo.is_device_ignored_sync("@device:pnp:non_existent") is False

        ignored = repo.get_ignored_devices_sync()
        assert len(ignored) == 1
        assert ignored[0]["device_path"] == "@device:pnp:ignored_01"

        # 3. Remover de ignorados
        removed = repo.remove_ignored_device_sync("@device:pnp:ignored_01")
        assert removed is True
        assert repo.is_device_ignored_sync("@device:pnp:ignored_01") is False


def test_json_to_sqlite_migration():
    """Valida la migración automática de config.json hacia SQLite WAL con backup."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "rtms.db")
        json_path = os.path.join(tmp_dir, "config.json")

        json_data = {
            "version": "2.4.1",
            "config_schema_version": 4,
            "cameras": {
                "@device:pnp:migrated": {
                    "id": "cam_migrated",
                    "friendly_name": "Migrated Cam",
                    "resolution": "720p",
                    "fps": 30,
                    "bitrate": 3000,
                    "encoder": "libx264",
                    "port": 9100,
                    "protocol": "srt",
                    "srt_latency": 120,
                    "srt_passphrase": "",
                    "zerolatency": True,
                    "auto_start": False,
                }
            },
            "ignored_devices": [{"device_path": "@device:pnp:ign", "friendly_name": "Ign Cam"}],
            "next_port": 9101,
            "unattended_autostart": False,
            "mediamtx_srt_port": 8890,
        }
        import json

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f)

        # Migrar a SQLite
        init_db(db_path)
        repo = ConfigRepository(db_path=db_path)
        # Reemplazar ruta global temporalmente para la prueba
        from unittest.mock import patch

        with (
            patch("core.repository.migrator.get_db_path", return_value=db_path),
            patch("core.repository.migrator.config_repository", repo),
        ):
            success = auto_migrate_json_to_sqlite(json_path=json_path)
            assert success is True

            # Backup .v2.4.1.bak debe existir
            backup_file = f"{json_path}.v2.4.1.bak"
            assert os.path.exists(backup_file)

            # La cámara debe estar en SQLite
            cams = repo.get_all_cameras_sync()
            assert "@device:pnp:migrated" in cams
            assert cams["@device:pnp:migrated"]["friendly_name"] == "Migrated Cam"

            # Exportar réplica
            replica_path = os.path.join(tmp_dir, "replica.json")
            with patch("core.repository.migrator.get_db_path", return_value=db_path):
                exported = export_sqlite_to_json(replica_path)
                assert exported is True
                assert os.path.exists(replica_path)


@pytest.mark.asyncio
async def test_system_settings_api():
    """Valida los endpoints GET y POST /api/system/settings."""
    test_token = "test_token_resilience_12345678"
    app = create_app(token=test_token)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"X-RTMS-Token": test_token}

        # 1. GET settings
        get_res = await ac.get("/api/system/settings", headers=headers)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["status"] == "ok"
        assert "mediamtx_srt_port" in get_data

        # 2. POST settings con puerto inválido
        bad_res = await ac.post(
            "/api/system/settings",
            headers=headers,
            json={"mediamtx_srt_port": 999999},  # Fuera de rango
        )
        assert bad_res.status_code == 422

        # 3. POST settings con autostart
        update_res = await ac.post(
            "/api/system/settings",
            headers=headers,
            json={"unattended_autostart": False},
        )
        assert update_res.status_code == 200
        assert update_res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_stream_proc_state_transitions():
    """Valida la máquina de estados de StreamProc sin acoplamientos espurios."""
    proc = StreamProc(device_path="@device:pnp:virtual_test")
    assert proc.state == State.STOPPED

    proc.transition_to(State.STARTING)
    assert proc.state == State.STARTING

    proc.transition_to(State.RUNNING)
    assert proc.state == State.RUNNING

    proc.transition_to(State.DISCONNECTED)
    assert proc.state == State.DISCONNECTED
    assert proc.is_alive is False


@pytest.mark.asyncio
async def test_mediamtx_manager_inactive_methods():
    """Valida los métodos de MediaMTXManager cuando el servidor no está en ejecución."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = MediaMTXManager(base_dir=tmp_dir)
        assert mgr.is_running() is False
        assert await mgr.get_paths() == []
        mgr.stop()
        assert mgr.is_running() is False


@pytest.mark.asyncio
async def test_config_repository_async_crud():
    """Valida las operaciones asíncronas con aiosqlite de ConfigRepository."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "async_rtms.db")
        init_db(db_path)
        repo = ConfigRepository(db_path=db_path)

        # 1. Dispositivos ignorados async
        await repo.add_ignored_device("@device:pnp:async_cam", "Async Camera")
        ignored = await repo.get_ignored_devices()
        assert len(ignored) == 1
        assert ignored[0]["device_path"] == "@device:pnp:async_cam"

        # 2. Cámaras async
        repo.save_camera_sync(
            "@device:pnp:async_cam",
            {"friendly_name": "Async Camera", "port": 9200, "protocol": "srt"},
        )
        cams = await repo.get_all_cameras()
        assert "@device:pnp:async_cam" in cams

        # 3. Remover y limpiar ignorados async
        removed = await repo.remove_ignored_device("@device:pnp:async_cam")
        assert removed is True
        await repo.add_ignored_device("@device:pnp:ign2", "Ignored 2")
        await repo.clear_ignored_devices()
        ignored_after = await repo.get_ignored_devices()
        assert len(ignored_after) == 0

        # 4. Eliminar cámara sync
        deleted = repo.delete_camera_sync("@device:pnp:async_cam")
        assert deleted is True
        cams_after = await repo.get_all_cameras()
        assert "@device:pnp:async_cam" not in cams_after


@pytest.mark.asyncio
async def test_command_builder_srt_publisher_no_passphrase():
    """Valida que FFmpeg como publisher en loopback SRT no incluya passphrase para evitar BADSECRET."""
    from core.command_builder import build_ffmpeg_command

    camera_cfg = {
        "id": "cam_secure_01",
        "device_path": "@device:pnp:\\\\?\\usb#test",
        "friendly_name": "Test Secure Cam",
        "resolution": "1080p",
        "fps": 30,
        "bitrate": 4000,
        "encoder": "libx264",
        "port": 9055,
        "protocol": "srt",
        "srt_latency": 120,
        "srt_passphrase": "SecretPassphrase123!",
        "zerolatency": True,
    }
    cmd, _, _ = await build_ffmpeg_command(camera_cfg)
    # El destino (último argumento de ffmpeg) debe ser srt://127.0.0.1:8890 con streamid=publish:cam_secure_01
    dest_url = cmd[-1]
    assert dest_url.startswith("srt://127.0.0.1:")
    assert "streamid=publish:cam_secure_01" in dest_url
    assert "passphrase=" not in dest_url


def test_mediamtx_config_generation_with_srt_passphrase():
    """Valida mitigación CWE-312: no almacenar contraseñas en disco y sincronizarlas en memoria vía API."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_rtms.db")
        init_db(db_path)
        repo = ConfigRepository(db_path=db_path)

        camera_cfg = {
            "id": "cam_enc_02",
            "friendly_name": "Encrypted Camera",
            "port": 9060,
            "protocol": "srt",
            "srt_passphrase": "ProtectedPass1234",
        }
        repo.save_camera_sync("@device:pnp:enc_02", camera_cfg)

        mgr = MediaMTXManager(base_dir=tmp_dir)

        with patch("core.repository.config_repository", repo):
            cfg_path = mgr.generate_config(srt_port=8890)

        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()

        # CWE-312: No exponer contraseñas en texto plano en archivo de configuración en disco
        assert "paths:" in content
        assert "all_others:" in content
        assert "ProtectedPass1234" not in content

        # Validar sincronización en memoria mediante API
        with patch.object(mgr, "_apply_path_api_sync") as mock_apply:
            with patch.object(mgr, "is_running", return_value=True):
                with patch("core.repository.config_repository", repo):
                    asyncio.run(mgr.sync_paths_api())
            mock_apply.assert_called_once_with("cam_enc_02", "ProtectedPass1234")


@pytest.mark.asyncio
async def test_stream_manager_network_error_not_device_lost():
    """Valida que errores de red/salida de FFmpeg se clasifiquen como NETWORK y no como DEVICE."""
    from unittest.mock import AsyncMock

    from core.stream_manager import ErrorCategory, StreamManager
    from core.stream_proc import StreamProc

    sm = StreamManager()
    proc = StreamProc(device_path="@device:pnp:test_net_error")
    sm._procs[proc.device_path] = proc

    fake_stderr_lines = [
        b"Output #0, mpegts, to 'srt://127.0.0.1:8890?streamid=publish:cam_test':\n",
        b"[srt @ 000001f3a2] Connection to srt://127.0.0.1:8890 failed: I/O error\n",
        b"Error opening output srt://127.0.0.1:8890: I/O error\n",
    ]

    class FakeProcess:
        def __init__(self, lines):
            self.stderr = self._gen(lines)

        async def _gen(self, lines):
            for line in lines:
                yield line

    mock_handle_device_lost = AsyncMock()
    sm._handle_device_lost = mock_handle_device_lost

    await sm._collect_logs(proc.device_path, FakeProcess(fake_stderr_lines))

    # Debe ser NETWORK
    assert proc.last_error_category == ErrorCategory.NETWORK
    # NO debe haber llamado a _handle_device_lost
    mock_handle_device_lost.assert_not_called()


@pytest.mark.asyncio
async def test_stream_preview_and_ffplay_use_mediamtx_port_and_streamid():
    """Valida que las URLs de vista previa y FFplay consuman desde MediaMTX con streamid=read."""
    from core.mediamtx_mgr import clean_camera_id, mediamtx_manager
    from core.stream_proc import build_stream_url

    mediamtx_port = mediamtx_manager.get_srt_port()
    clean_id = clean_camera_id("cam-01 test")

    preview_url = build_stream_url(
        protocol="srt",
        port=mediamtx_port,
        passphrase="ReaderPassword123",
        mode="caller",
        latency_ms=120,
        zerolatency=True,
        streamid=f"read:{clean_id}",
    )

    assert f":{mediamtx_port}" in preview_url
    assert f"streamid=read:{clean_id}" in preview_url
    assert "passphrase=ReaderPassword123" in preview_url
    assert "mode=caller" in preview_url


def test_sqlite_wal_recovery_when_json_missing():
    """Valida la recuperación bidireccional desde SQLite WAL cuando config.json se pierde o elimina."""
    from unittest.mock import patch

    import core.config_mgr as cm

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "rtms.db")
        json_path = os.path.join(tmp_dir, "config.json")
        bak_path = os.path.join(tmp_dir, "config.json.bak")
        init_db(db_path)
        repo = ConfigRepository(db_path=db_path)

        # 1. Guardar cámara directamente en SQLite WAL
        sample_cam = {
            "id": "cam_recovered_db",
            "friendly_name": "Recovered DB Cam",
            "resolution": "1080p",
            "fps": 60,
            "bitrate": 4500,
            "port": 9070,
            "protocol": "srt",
        }
        repo.save_camera_sync("@device:pnp:recovered_01", sample_cam)

        # Asegurar que config.json y config.bak no existan
        assert not os.path.exists(json_path)
        assert not os.path.exists(bak_path)

        with (
            patch.object(cm, "CONFIG_FILE", json_path),
            patch.object(cm, "CONFIG_BAK_FILE", bak_path),
            patch.object(cm, "CONFIG_DIR", tmp_dir),
            patch("core.repository.config_repository.config_repository", repo),
            patch("core.repository.migrator.config_repository", repo),
            patch("core.repository.database.get_db_path", return_value=db_path),
            patch("core.repository.migrator.get_db_path", return_value=db_path),
        ):
            loaded = cm.load_config()
            assert "@device:pnp:recovered_01" in loaded.get("cameras", {})
            assert loaded["cameras"]["@device:pnp:recovered_01"]["friendly_name"] == "Recovered DB Cam"
            # Y config.json debe haberse restaurado en disco
            assert os.path.exists(json_path)


@pytest.mark.asyncio
async def test_stream_manager_watchdog_lifecycle_in_task_registry():
    """Valida que el watchdog de StreamManager se registre en TaskRegistry y se cancele limpiamente en stop_all."""
    from unittest.mock import patch

    from core.stream_manager import StreamManager
    from core.task_registry import TaskRegistry

    test_registry = TaskRegistry()
    sm = StreamManager()

    with (
        patch("core.task_registry.task_registry", test_registry),
        patch("core.stream_manager.get_directshow_devices", return_value=[]),
    ):
        await sm.sync_streams_with_hardware()

        # El watchdog debe estar registrado
        assert sm._watchdog_task is not None
        assert not sm._watchdog_task.done()

        # Debe estar en el registro de tareas activas
        assert sm._watchdog_task in test_registry.active_tasks

        # Al llamar a stop_all, debe cancelarse y quedar en None
        await sm.stop_all()
        assert sm._watchdog_task is None
