# ==============================================================================
# RTMS v2.2.0 — Tests Unitarios de Ciclo de Vida de Streams (core/ffmpeg_mgr.py)
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import asyncio
from core.ffmpeg_mgr import StreamProc, State

def test_stream_proc_initial_state():
    """Valida los estados iniciales por defecto de StreamProc."""
    proc = StreamProc("@device_test_lifecycle")
    assert proc.state == State.STOPPED
    assert proc.error_count == 0
    assert proc.is_alive is False
    assert proc.using_fallback_cpu is False
    assert proc.permanent_failure is False

def test_state_enum_values():
    """Valida que todos los estados formales del ciclo de vida estén definidos."""
    expected_states = ["stopped", "starting", "running", "error", "restarting", "stopping", "disconnected"]
    for s in expected_states:
        assert State(s) in list(State)

def test_stream_proc_lock_prevents_race_condition():
    """Valida que el lock de StreamProc garantice exclusión mutua."""
    async def _run():
        proc = StreamProc("@device_lock_test")
        counter = 0

        async def critical_section():
            nonlocal counter
            async with proc.lock:
                val = counter
                await asyncio.sleep(0.01)
                counter = val + 1

        await asyncio.gather(critical_section(), critical_section(), critical_section())
        assert counter == 3

    asyncio.run(_run())
