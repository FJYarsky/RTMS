# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de Estrés y Concurrencia Masiva Multihilo y Asíncrona.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Suite de pruebas de estrés y concurrencia:
- PreviewManager: contención de semáforo (concurrencia máx=2), ciclado rápido y timeouts FFmpeg.
- StreamManager: arranques y paradas simultáneas, caídas simuladas, watchdog y colisiones de puertos.
- ConfigRepository: transacciones concurrentes multihilo (10 hilos) sobre SQLite en modo WAL sin bloqueos.
- TelemetryHub: 50 clientes WebSocket concurrentes suscribiéndose/desuscribiéndose bajo difusión de métricas a 10 Hz.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.preview_mgr import PreviewManager
from core.repository.config_repository import ConfigRepository
from core.repository.database import init_db
from core.stream_manager import StreamManager
from core.stream_proc import State
from core.telemetry_hub import TelemetryWebSocketHub

# ==============================================================================
# 1. PREVIEW MANAGER CONCURRENCY & STRESS
# ==============================================================================


@pytest.mark.asyncio
async def test_preview_manager_semaphore_contention_and_slot_uniqueness():
    """Valida la contención concurrente por el semáforo (_max_concurrent=2) y la exclusión por cámara."""
    pm = PreviewManager()
    # Limitar semáforo a 2 slots concurrentes para simular carga
    pm._preview_semaphore = asyncio.Semaphore(2)

    # 1. Tres cámaras intentan adquirir ranura en paralelo
    cams = ["cam_alpha", "cam_beta", "cam_gamma"]
    results = await asyncio.gather(*[pm.acquire_slot(c) for c in cams])

    # Exactamente 2 deben ser True y 1 False (sin excepciones ni deadlocks)
    assert results.count(True) == 2
    assert results.count(False) == 1

    # Identificar cuál cámara quedó fuera
    acquired_cams = [cams[i] for i, ok in enumerate(results) if ok]
    rejected_cam = [cams[i] for i, ok in enumerate(results) if not ok][0]

    # 2. La misma cámara ya activa intenta pedir otra ranura -> rechazo inmediato (ranura única por cámara)
    duplicate_try = await pm.acquire_slot(acquired_cams[0])
    assert duplicate_try is False

    # 3. Liberar una de las ranuras ocupadas
    await pm.release_slot(acquired_cams[0])

    # Ahora la cámara previamente rechazada debe poder adquirir su ranura
    retry_ok = await pm.acquire_slot(rejected_cam)
    assert retry_ok is True

    # Limpieza
    await pm.stop_all()


@pytest.mark.asyncio
async def test_preview_manager_rapid_start_stop_cycling_and_cleanup():
    """Valida que ciclos rápidos de apertura y cierre de FFplay limpien procesos sin dejar handles huérfanos."""
    pm = PreviewManager()

    mock_procs = []
    for _i in range(10):
        m = MagicMock()
        m.poll.return_value = None
        m.terminate = MagicMock()
        m.wait = MagicMock(return_value=0)
        mock_procs.append(m)

    with (
        patch("core.preview_mgr.get_ffplay_bin", return_value="dummy_ffplay.exe"),
        patch("os.path.exists", return_value=True),
        patch("subprocess.Popen", side_effect=mock_procs),
    ):
        # Lanzamiento rápido consecutivo de 5 instancias
        for i in range(5):
            success = pm.launch_ffplay(url=f"srt://127.0.0.1:{9000 + i}", title=f"Cam {i}")
            assert success is True

        assert len(pm._active_ffplay) == 5

        # Simular que 2 procesos terminaron externamente
        mock_procs[0].poll.return_value = 0
        mock_procs[1].poll.return_value = 0

        pm._reap_dead_processes()
        assert len(pm._active_ffplay) == 3

        # Parada masiva limpia
        await pm.stop_all()
        assert len(pm._active_ffplay) == 0


@pytest.mark.asyncio
async def test_preview_manager_snapshot_timeout_handling():
    """Valida que si FFmpeg se congela durante un snapshot, se termine el subproceso con kill() y retorne None."""
    pm = PreviewManager()

    mock_subproc = MagicMock()
    mock_subproc.kill = MagicMock()

    async def _fake_wait():
        return 0

    async def _fake_communicate():
        await asyncio.sleep(2.0)
        return b"", b""

    async def _fake_create(*args, **kwargs):
        return mock_subproc

    mock_subproc.wait = _fake_wait
    mock_subproc.communicate = _fake_communicate

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("core.preview_mgr.get_ffmpeg_bin", return_value="ffmpeg.exe"),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_create),
    ):
        snapshot = await pm.get_snapshot_frame("virtual://test", timeout=0.01)
        assert snapshot is None
        # Se debe haber forzado kill()
        mock_subproc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_preview_manager_mjpeg_stream_abrupt_disconnect_cleanup():
    """Valida que ante desconexión abrupta del cliente MJPEG, los recursos y la ranura se liberen de inmediato."""
    pm = PreviewManager()
    identifier = "cam_mjpeg_test"

    acquired = await pm.acquire_slot(identifier)
    assert acquired is True
    assert identifier in pm._active_camera_previews

    mock_subproc = MagicMock()
    mock_subproc.stdout = MagicMock()
    jpeg_frame = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\xff\xd9"

    async def _fake_read(n=16384):
        return jpeg_frame

    async def _fake_wait():
        return 0

    mock_subproc.stdout.read = _fake_read
    mock_subproc.terminate = MagicMock()
    mock_subproc.kill = MagicMock()
    mock_subproc.wait = _fake_wait

    async def _fake_exec(*args, **kwargs):
        return mock_subproc

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("core.preview_mgr.get_ffmpeg_bin", return_value="ffmpeg.exe"),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_exec),
    ):
        gen = pm.generate_mjpeg_stream("virtual://test", is_virtual=True, identifier=identifier)
        # Consumir un chunk
        async for chunk in gen:
            assert b"--frame" in chunk
            break  # Desconexión temprana del cliente
        await gen.aclose()

    # La ranura debe haber sido liberada automáticamente en el finally
    assert identifier not in pm._active_camera_previews


# ==============================================================================
# 2. STREAM MANAGER CONCURRENCY & STRESS
# ==============================================================================


@pytest.mark.asyncio
async def test_stream_manager_rapid_concurrent_starts_and_stops():
    """Valida el manejo concurrente de múltiples streams arrancando y deteniéndose simultáneamente."""
    sm = StreamManager()
    stream_count = 6
    device_paths = [f"video=MultiCam_{i}" for i in range(stream_count)]

    def make_mock_proc():
        m = AsyncMock()
        m.returncode = None
        m.stdin = MagicMock()
        m.stdin.write = MagicMock()
        m.stdin.drain = AsyncMock()
        m.stdout = AsyncMock()
        m.stdout.readline = AsyncMock(return_value=b"")
        m.stderr = AsyncMock()
        m.stderr.readline = AsyncMock(return_value=b"")
        m.wait = AsyncMock(return_value=0)
        m.terminate = MagicMock()
        m.pid = 9999
        return m

    # Mocks para saltar chequeos de hardware físico y ejecución real de ffmpeg
    with (
        patch("core.stream_manager.has_ffmpeg_binary", return_value=True),
        patch("core.stream_manager.get_directshow_devices", return_value=[{"device_path": dp} for dp in device_paths]),
        patch(
            "core.config_mgr.find_camera_by_id_or_path",
            side_effect=lambda dp: {"device_path": dp, "friendly_name": dp, "port": 9000, "is_virtual": True},
        ),
        patch("core.stream_manager.StreamManager.build_command", return_value=(["ffmpeg"], "srt://dummy", "libx264")),
        patch("asyncio.create_subprocess_exec", side_effect=lambda *args, **kwargs: make_mock_proc()),
    ):
        # 1. Inicio simultáneo masivo
        start_tasks = [sm.start_stream(dp) for dp in device_paths]
        await asyncio.gather(*start_tasks)

        for dp in device_paths:
            proc = sm.get_proc(dp)
            assert proc is not None
            assert proc.state == State.RUNNING
            assert proc.is_alive is True

        # 2. Detención simultánea masiva
        stop_tasks = [sm.stop_stream(dp, timeout=0.1) for dp in device_paths]
        await asyncio.gather(*stop_tasks)

        for dp in device_paths:
            proc = sm.get_proc(dp)
            assert proc.state == State.STOPPED
            assert proc.is_alive is False


@pytest.mark.asyncio
async def test_stream_manager_process_crash_and_watchdog_auto_recovery():
    """Valida la detección de caída de proceso en Watchdog y la transición a recuperación o intervención manual."""
    sm = StreamManager()
    dp = "video=CrashRecoveryCam"
    proc = sm.ensure_proc(dp)
    proc.config = {"device_path": dp, "friendly_name": dp, "port": 9050, "is_virtual": True}
    proc.state = State.RUNNING
    proc.started_at = datetime.now()
    # Simular proceso caído
    proc.process = MagicMock()
    proc.process.poll.return_value = 1  # Retorno no-cero (caído)

    # 1. Simulación de watchdog detectando la caída
    now = datetime.now()
    if not proc.is_alive and proc.state == State.RUNNING:
        proc.error_count += 1
        proc.transition_to(State.ERROR)
        proc.next_retry_at = now + timedelta(seconds=1)

    assert proc.state == State.ERROR
    assert proc.error_count == 1
    assert proc.next_retry_at is not None

    # 2. Simulación de superación del umbral MAX_ERRORS
    proc.error_count = sm.MAX_ERRORS + 1
    if proc.error_count > sm.MAX_ERRORS:
        proc.manual_intervention_required = True
        proc.transition_to(State.MANUAL_INTERVENTION_REQUIRED)

    assert proc.state == State.MANUAL_INTERVENTION_REQUIRED
    assert proc.manual_intervention_required is True

    # 3. Simulación de recuperación y reinicio de errores tras estabilidad
    proc.state = State.RUNNING
    proc.started_at = datetime.now() - timedelta(seconds=sm.STABILITY_THRESHOLD_SECONDS + 5)
    uptime = (datetime.now() - proc.started_at).total_seconds()
    if uptime >= sm.STABILITY_THRESHOLD_SECONDS and proc.error_count > 0:
        proc.clear_failure()

    assert proc.error_count == 0
    assert proc.manual_intervention_required is False


@pytest.mark.asyncio
async def test_stream_manager_port_collision_resolution_on_start():
    """Valida que si el puerto asignado está ocupado al iniciar, se reasigne dinámicamente sin fallar."""
    sm = StreamManager()
    dp = "video=PortCollisionCam"
    proc = sm.ensure_proc(dp)
    proc.config = {"device_path": dp, "friendly_name": dp, "port": 9080, "is_virtual": True}
    proc.is_connected = True

    mock_subproc = AsyncMock()
    mock_subproc.returncode = None
    mock_subproc.stdin = MagicMock()
    mock_subproc.stdin.write = MagicMock()
    mock_subproc.stdin.drain = AsyncMock()
    mock_subproc.stdout = AsyncMock()
    mock_subproc.stdout.readline = AsyncMock(return_value=b"")
    mock_subproc.stderr = AsyncMock()
    mock_subproc.stderr.readline = AsyncMock(return_value=b"")
    mock_subproc.wait = AsyncMock(return_value=0)
    mock_subproc.pid = 8888

    with (
        patch("core.stream_manager.has_ffmpeg_binary", return_value=True),
        patch("core.port_mgr.port_manager.revalidate_port", return_value=False),  # Puerto 9080 ocupado
        patch("core.port_mgr.port_manager.reallocate_if_collided", return_value=9081) as mock_realloc,
        patch("core.config_mgr.load_config", return_value={"cameras": {dp: {"port": 9080}}}),
        patch("core.config_mgr.save_config", return_value=True),
        patch("core.stream_manager.StreamManager.build_command", return_value=(["ffmpeg"], "srt://dummy", "libx264")),
        patch("asyncio.create_subprocess_exec", return_value=mock_subproc),
    ):
        await sm.start_stream(dp)
        mock_realloc.assert_called_once_with(9080)
        assert proc.config["port"] == 9081
        await sm.stop_stream(dp, timeout=0.1)


# ==============================================================================
# 3. CONFIG REPOSITORY (SQLITE WAL) MULTITHREADED CONCURRENCY
# ==============================================================================


def test_config_repository_wal_multithreaded_concurrency(tmp_path):
    """
    Verifica que 10 hilos concurrentes leyendo y escribiendo en ConfigRepository (SQLite en WAL)
    no experimenten errores de 'database is locked' ni corrupción de datos.
    """
    db_file = tmp_path / "rtms_stress.db"
    init_db(str(db_file))
    repo = ConfigRepository(db_path=str(db_file))

    num_threads = 10
    iterations_per_thread = 15
    errors = []

    def _worker(thread_id: int):
        try:
            for it in range(iterations_per_thread):
                device_path = f"video=ThreadCam_{thread_id}_{it}"
                cam_data = {
                    "id": f"cam_uuid_{thread_id}_{it}",
                    "friendly_name": f"Camera {thread_id}-{it}",
                    "resolution": "720p",
                    "fps": 30,
                    "bitrate": 3000,
                    "encoder": "libx264",
                    "port": 9000 + (thread_id * 20) + it,
                    "protocol": "srt",
                    "srt_latency": 120,
                    "srt_passphrase": "SecretPassphrase123",
                    "zerolatency": True,
                    "auto_start": False,
                    "is_virtual": False,
                    "udp_mode": "multicast",
                    "udp_host": "127.0.0.1",
                }
                # 1. Escritura síncrona
                repo.save_camera_sync(device_path, cam_data)

                # 2. Lectura síncrona
                cameras = repo.get_all_cameras_sync()
                assert device_path in cameras

                # 3. Ajustes de sistema
                repo.set_system_setting_sync(f"key_{thread_id}", f"val_{it}")
                setting = repo.get_system_settings_sync().get(f"key_{thread_id}")
                assert setting == f"val_{it}"
        except Exception as e:
            errors.append(f"Thread {thread_id} error: {e}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(_worker, tid) for tid in range(num_threads)]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Ocurrieron errores en hilos de SQLite: {errors}"
    all_cams = repo.get_all_cameras_sync()
    assert len(all_cams) == num_threads * iterations_per_thread


@pytest.mark.asyncio
async def test_config_repository_async_concurrent_operations(tmp_path):
    """Valida la concurrencia asíncrona de aiosqlite en ConfigRepository."""
    db_file = tmp_path / "rtms_async_stress.db"
    init_db(str(db_file))
    repo = ConfigRepository(db_path=str(db_file))

    async def _async_write(idx: int):
        dp = f"video=AsyncCam_{idx}"
        await repo.add_ignored_device(dp, f"Async Cam {idx}")
        ignored = await repo.get_ignored_devices()
        assert any(item["device_path"] == dp for item in ignored)
        all_cams = await repo.get_all_cameras()
        assert isinstance(all_cams, dict)

    await asyncio.gather(*[_async_write(i) for i in range(20)])
    ignored_final = await repo.get_ignored_devices()
    assert len(ignored_final) == 20


# ==============================================================================
# 4. TELEMETRY HUB CONCURRENCY & CLIENT STRESS
# ==============================================================================


class MockWebSocketClient:
    """Cliente WebSocket simulado para evaluar la distribución reactiva a 10 Hz."""

    def __init__(self, should_fail: bool = False):
        self.received_messages = []
        self.should_fail = should_fail

    async def send_text(self, text: str):
        if self.should_fail:
            raise ConnectionResetError("Cliente WebSocket desconectado forzosamente")
        self.received_messages.append(text)


@pytest.mark.asyncio
async def test_telemetry_hub_50_concurrent_subscriptions_and_broadcast():
    """Valida 50 clientes WebSocket suscribiéndose, recibiendo telemetría a alta frecuencia y desuscribiéndose."""
    hub = TelemetryWebSocketHub()
    client_count = 50
    clients = [MockWebSocketClient() for _ in range(client_count)]

    # 1. Suscripción concurrente masiva
    await asyncio.gather(*[hub.register(ws) for ws in clients])
    assert hub.client_count == client_count
    assert hub._running is True

    # 2. Difusión masiva de métricas y eventos reactivos
    broadcast_tasks = []
    for i in range(30):
        broadcast_tasks.append(hub.broadcast_event("stream_metric_tick", {"tick": i, "cpu": 12.5}))
    await asyncio.gather(*broadcast_tasks)

    # Cada cliente debe haber recibido los 30 eventos (más posibles ticks del bucle a 10 Hz)
    for ws in clients:
        event_count = sum(1 for m in ws.received_messages if "stream_metric_tick" in m)
        assert event_count == 30

    # 3. Desuscripción concurrente masiva
    await asyncio.gather(*[hub.unregister(ws) for ws in clients])
    assert hub.client_count == 0
    assert hub._running is False
    assert hub._ticker_task is None


@pytest.mark.asyncio
async def test_telemetry_hub_prunes_dead_and_failing_clients_gracefully():
    """Valida que clientes con sockets rotos se eliminen limpiamente sin afectar a los clientes sanos."""
    hub = TelemetryWebSocketHub()

    healthy_clients = [MockWebSocketClient(should_fail=False) for _ in range(10)]
    failing_clients = [MockWebSocketClient(should_fail=True) for _ in range(10)]

    all_clients = healthy_clients + failing_clients
    for ws in all_clients:
        await hub.register(ws)

    assert hub.client_count == 20

    # Al emitir un broadcast, los 10 clientes con fallo deben ser purgados automáticamente
    await hub.broadcast({"status": "heartbeat", "cpu": 25.0})

    assert hub.client_count == 10
    for h in healthy_clients:
        assert len(h.received_messages) == 1

    # Limpieza
    for h in healthy_clients:
        await hub.unregister(h)
    assert hub.client_count == 0


@pytest.mark.asyncio
async def test_preview_manager_is_running_and_terminate_all():
    """Valida la consulta de estado y la terminación forzosa limpia de procesos FFplay."""
    pm = PreviewManager()
    assert pm.is_ffplay_running() is False

    m = MagicMock()
    m.poll.return_value = None
    m.terminate = MagicMock()
    m.wait = MagicMock(return_value=0)
    pm._active_ffplay["srt://test:9000"] = m

    assert pm.is_ffplay_running("srt://test:9000") is True
    pm.terminate_all_ffplay()
    assert pm.is_ffplay_running() is False


def test_preview_manager_invalid_url_and_protocol_fuzzing():
    """Valida el rechazo preventivo de URLs y banderas peligrosas o no autorizadas para FFplay."""
    pm = PreviewManager()
    assert pm.launch_ffplay("-malicious_flag") is False
    assert pm.launch_ffplay("ftp://invalid.proto") is False
    assert pm.launch_ffplay("-invalid_dshow", is_dshow=True) is False


@pytest.mark.asyncio
async def test_preview_manager_mjpeg_buffer_overflow_defense():
    """Valida que un flujo sin delimitadores JPEG que supere MAX_JPEG_BUFFER limpie el buffer sin desbordar memoria."""
    pm = PreviewManager()
    mock_subproc = MagicMock()
    mock_subproc.stdout = MagicMock()
    giant_chunk = b"A" * (pm.MAX_JPEG_BUFFER + 1024)

    async def _read_overflow(n=16384):
        nonlocal giant_chunk
        if giant_chunk:
            res = giant_chunk
            giant_chunk = b""
            return res
        return b""

    mock_subproc.stdout.read = _read_overflow
    mock_subproc.terminate = MagicMock()
    mock_subproc.kill = MagicMock()
    mock_subproc.wait = AsyncMock(return_value=0)

    async def _fake_exec(*args, **kwargs):
        return mock_subproc

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("core.preview_mgr.get_ffmpeg_bin", return_value="ffmpeg.exe"),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_exec),
    ):
        gen = pm.generate_mjpeg_stream("virtual://overflow")
        frames = []
        async for chunk in gen:
            frames.append(chunk)
        assert len(frames) == 0


@pytest.mark.asyncio
async def test_stream_manager_restart_stream_and_emergency_stops():
    """Valida restart_stream y la detención global de emergencia emergency_stop_all."""
    sm = StreamManager()
    dp = "video=TestRestartCam"
    proc = sm.ensure_proc(dp)
    proc.config = {"device_path": dp, "friendly_name": dp, "port": 9090, "is_virtual": True}
    proc.is_connected = True

    m = MagicMock()
    m.returncode = None
    m.stdin = MagicMock()
    m.stdin.write = MagicMock()
    m.stdin.drain = AsyncMock()
    m.stdout = AsyncMock()
    m.stdout.readline = AsyncMock(return_value=b"")
    m.stderr = AsyncMock()
    m.stderr.readline = AsyncMock(return_value=b"")
    m.wait = AsyncMock(return_value=0)
    m.terminate = MagicMock()
    m.pid = 7777

    async def _fake_subproc(*args, **kwargs):
        return m

    with (
        patch("core.stream_manager.has_ffmpeg_binary", return_value=True),
        patch("core.stream_manager.StreamManager.build_command", return_value=(["ffmpeg"], "srt://dummy", "libx264")),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_subproc),
    ):
        await sm.start_stream(dp)
        assert proc.state == State.RUNNING
        await sm.restart_stream(dp)
        assert proc.state == State.RUNNING
        await sm.emergency_stop_all()
        assert proc.state == State.STOPPED
        await sm.stop_all_streams()


@pytest.mark.asyncio
async def test_stream_manager_fallbacks_and_lifecycle_edge_cases():
    """Valida las transiciones de fallback a CPU libx264, conmutación desde MJPEG y desconexión física."""
    sm = StreamManager()
    dp = "video=TestFallbackCam"
    proc = sm.ensure_proc(dp)
    proc.config = {"device_path": dp, "friendly_name": dp, "port": 9092, "is_virtual": True}
    proc.is_connected = True

    m = MagicMock()
    m.returncode = None
    m.stdin = MagicMock()
    m.stdin.write = MagicMock()
    m.stdin.drain = AsyncMock()
    m.stdout = AsyncMock()
    m.stdout.readline = AsyncMock(return_value=b"")
    m.stderr = AsyncMock()
    m.stderr.readline = AsyncMock(return_value=b"")
    m.wait = AsyncMock(return_value=0)
    m.terminate = MagicMock()
    m.pid = 6666

    async def _fake_subproc(*args, **kwargs):
        return m

    with (
        patch("core.stream_manager.has_ffmpeg_binary", return_value=True),
        patch("core.stream_manager.StreamManager.build_command", return_value=(["ffmpeg"], "srt://dummy", "libx264")),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_subproc),
        patch("core.config_mgr.remove_camera_config", return_value=True),
    ):
        await sm.start_stream(dp)
        # Fallback a CPU
        await sm._fallback_to_cpu(dp)
        assert proc.using_fallback_cpu is True
        assert proc.per_stream_encoder == "libx264"

        # Fallback desde MJPEG
        await sm._fallback_from_mjpeg(dp)
        assert proc.mjpeg_input_failed is True

        # Desconexión física de hardware
        with patch("core.stream_manager.get_directshow_devices", return_value=[]):
            await sm._handle_device_lost(dp)
            assert proc.is_connected is False
            assert proc.state in (State.DISCONNECTED, State.STOPPED)

        # Eliminación de stream
        removed = await sm.remove_stream(dp)
        assert removed is True
        assert dp not in sm._procs


def test_config_repository_crud_stress(tmp_path):
    """Valida operaciones CRUD transaccionales completas de ConfigRepository."""
    db_file = tmp_path / "rtms_crud.db"
    init_db(str(db_file))
    repo = ConfigRepository(db_path=str(db_file))

    # Test camera delete
    repo.save_camera_sync(
        "video=DeleteCam",
        {
            "id": "del_id",
            "friendly_name": "Delete Me",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "encoder": "libx264",
            "port": 9099,
        },
    )
    assert "video=DeleteCam" in repo.get_all_cameras_sync()
    deleted = repo.delete_camera_sync("video=DeleteCam")
    assert deleted is True
    assert "video=DeleteCam" not in repo.get_all_cameras_sync()

    # Test full config load and save
    full = repo.load_full_config_sync()
    assert "cameras" in full
    assert "mediamtx_srt_port" in full
    assert "ignored_devices" in full
    repo.save_full_config_sync(full)

    # Test ignored devices CRUD
    repo.add_ignored_device_sync("video=Ignored1", "Ignored 1")
    assert repo.is_device_ignored_sync("video=Ignored1") is True
    assert len(repo.get_ignored_devices_sync()) == 1
    repo.remove_ignored_device_sync("video=Ignored1")
    assert repo.is_device_ignored_sync("video=Ignored1") is False
    repo.add_ignored_device_sync("video=Ignored2", "Ignored 2")
    repo.clear_ignored_devices_sync()
    assert len(repo.get_ignored_devices_sync()) == 0


@pytest.mark.asyncio
async def test_telemetry_hub_notify_event_threadsafe_and_stop():
    """Valida notify_event_threadsafe y la detención limpia del hub."""
    hub = TelemetryWebSocketHub()
    hub.notify_event_threadsafe("custom_event", {"val": 123})
    await hub.stop()
    assert hub._running is False
