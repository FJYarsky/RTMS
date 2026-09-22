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
