# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del ciclo de vida de transmisiones y cámaras.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import asyncio
from core.config_mgr import generate_stable_camera_id, save_config, load_config
from core.ffmpeg_mgr import StreamManager, StreamProc, State, ErrorCategory
from fastapi.testclient import TestClient
from main import create_app

def test_camera_id_disambiguation():
    """TEST-09: generate_stable_camera_id generates distinct IDs for same VID/PID cameras on different ports."""
    # Two cameras with identical VID/PID but different physical USB hub/port paths
    path1 = r"@device_pnp_\\?\usb#vid_046d&pid_0825&mi_00#7&2a1b94b&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
    path2 = r"@device_pnp_\\?\usb#vid_046d&pid_0825&mi_00#7&3b2c05c&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"

    id1 = generate_stable_camera_id(path1)
    id2 = generate_stable_camera_id(path2)

    assert id1 != id2, "Cameras with identical VID/PID on different paths must have unique IDs"
    assert id1.startswith("cam_046d_0825_")
    assert id2.startswith("cam_046d_0825_")

def test_error_category_and_recovery_task_cleanup():
    """TEST-10: StreamProc transitions states and cleans up recovery_task properly on stop."""
    async def _run():
        proc = StreamProc("test_device")
        assert proc.state == State.STOPPED
        assert proc.last_error_category == ErrorCategory.UNKNOWN

        # Transition to starting then running
        proc.transition_to(State.STARTING)
        assert proc.state == State.STARTING

        proc.transition_to(State.RUNNING)
        assert proc.state == State.RUNNING

        # Attach dummy recovery task
        dummy_task = asyncio.create_task(asyncio.sleep(10))
        proc.recovery_task = dummy_task

        sm = StreamManager()
        sm._procs["test_device"] = proc

        # Stop stream locked must cancel and clear recovery task
        await sm._stop_stream_locked(proc)
        assert proc.recovery_task is None
        assert dummy_task.cancelled() or dummy_task.done()

    asyncio.run(_run())

def test_port_collision_detection_and_reallocation():
    """TEST-11: reallocate_if_collided allocates a new free port when collision is detected."""
    async def _run():
        proc = StreamProc("colliding_cam")
        proc.config = {"port": 9000, "protocol": "srt"}

        sm = StreamManager()
        new_port = await sm.reallocate_if_collided(proc)
        assert new_port is not None
        # Port must be assigned and config updated
        assert proc.config["port"] == new_port
        assert proc.last_error_category == ErrorCategory.PORT_COLLISION

    asyncio.run(_run())

def test_delete_camera_endpoint():
    """TEST-12: DELETE /api/stream/{device_path} deletes camera from memory and disk config."""
    token = "delete_test_token"
    app = create_app(token=token)
    client = TestClient(app)

    dp = "video=UsbCameraToDelete"
    cfg = {
        "version": "2.2.2",
        "cameras": {
            "cam_del_1": {
                "friendly_name": "Camera to Delete",
                "device_path": dp,
                "port": 9005
            }
        }
    }
    save_config(cfg)
    assert "cam_del_1" in load_config()["cameras"]

    # Call DELETE endpoint
    headers = {"X-RTMS-Token": token}
    res = client.delete(f"/api/stream/{dp}", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Verify camera was removed from disk
    reloaded = load_config()
    assert "cam_del_1" not in reloaded["cameras"]
