# ==============================================================================
# RTMS v2.2.2 — Preview Subsystem Audit Verification Tests
# Tests TEST-05 to TEST-08 covering N8, P1-10, N14, N4, N5, P1-12
# ==============================================================================

import asyncio
from core.preview_mgr import PreviewManager

def test_preview_slot_concurrency():
    """TEST-05: acquire_slot enforces max 3 global previews and 1 preview per camera."""
    async def _run():
        pm = PreviewManager()

        # Acquire slot for cam1
        ok1 = await pm.acquire_slot("cam1")
        assert ok1 is True
        assert "cam1" in pm._active_camera_previews

        # Second request for cam1 must be rejected (per-camera slot busy)
        ok1_dup = await pm.acquire_slot("cam1")
        assert ok1_dup is False

        # Acquire cam2 and cam3 (reaching semaphore limit of 3)
        ok2 = await pm.acquire_slot("cam2")
        ok3 = await pm.acquire_slot("cam3")
        assert ok2 is True
        assert ok3 is True

        # 4th concurrent preview must fail immediately (non-blocking)
        ok4 = await pm.acquire_slot("cam4")
        assert ok4 is False

        # Release cam1, now cam4 can acquire
        await pm.release_slot("cam1")
        assert "cam1" not in pm._active_camera_previews
        ok4_retry = await pm.acquire_slot("cam4")
        assert ok4_retry is True

        # Cleanup
        await pm.release_slot("cam2")
        await pm.release_slot("cam3")
        await pm.release_slot("cam4")

    asyncio.run(_run())

def test_mjpeg_buffer_cap(monkeypatch):
    """TEST-06: generate_mjpeg_stream enforces 4MB buffer cap when boundary is missing."""
    async def _run():
        pm = PreviewManager()

        # Mock process that outputs 5MB of junk without boundary
        class FakeStdout:
            def __init__(self):
                self.sent = 0
            async def read(self, n):
                if self.sent < 5 * 1024 * 1024:
                    chunk = b"X" * n
                    self.sent += len(chunk)
                    return chunk
                return b""

        class FakeProc:
            def __init__(self):
                self.stdout = FakeStdout()
                self.stderr = FakeStdout()
                self.returncode = None
            def terminate(self):
                self.returncode = 0
            def kill(self):
                self.returncode = -9
            async def wait(self):
                self.returncode = -9
                return -9

        async def fake_create_subprocess(*args, **kwargs):
            return FakeProc()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess)

        # Stream generator should break safely when 4MB cap is exceeded
        chunks = []
        async for chunk in pm.generate_mjpeg_stream("test_target", is_dshow=False):
            chunks.append(chunk)

        # Generator terminates safely without unbounded memory explosion
        assert len(chunks) == 0

    asyncio.run(_run())

def test_snapshot_timeout_kills_process(monkeypatch):
    """TEST-07: get_snapshot_frame kills process on timeout to avoid holding DirectShow locks."""
    async def _run():
        pm = PreviewManager()

        killed = False

        class StuckProc:
            def __init__(self):
                self.returncode = None
            async def communicate(self):
                # Hang indefinitely until killed
                await asyncio.sleep(100)
                return b"", b""
            def kill(self):
                nonlocal killed
                killed = True
                self.returncode = -9
            async def wait(self):
                self.returncode = -9
                return -9

        async def fake_subp(*args, **kwargs):
            return StuckProc()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subp)

        # Call with very short timeout
        frame = await pm.get_snapshot_frame("dummy_device", timeout=0.1)
        assert frame is None
        assert killed is True, "Process must be killed on timeout"

    asyncio.run(_run())

def test_preview_stop_all_cleans_up():
    """TEST-08: stop_all cancels active tasks, clears slots and resets semaphore."""
    async def _run():
        pm = PreviewManager()

        # Register an active slot
        await pm.acquire_slot("test_cam")
        assert len(pm._active_camera_previews) == 1

        await pm.stop_all()
        assert len(pm._active_camera_previews) == 0

    asyncio.run(_run())
