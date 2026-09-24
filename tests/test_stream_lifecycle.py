# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del ciclo de vida y estados de procesos de transmisión.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas del ciclo de vida y estados de procesos de transmisión."""

import asyncio

from core.stream_proc import State, StreamProc


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


def test_stream_proc_clear_failure_resets_zero_fps():
    """Valida que clear_failure limpie zero_fps_since y estado de fallo."""
    from datetime import datetime

    proc = StreamProc("@device_fps_test")
    proc.zero_fps_since = datetime.now()
    proc.error_count = 3
    proc.manual_intervention_required = True
    proc.state = State.ERROR

    proc.clear_failure()
    assert proc.zero_fps_since is None
    assert proc.error_count == 0
    assert proc.manual_intervention_required is False
    assert proc.state == State.STOPPED


def test_stream_manager_handle_device_lost_transitions_to_disconnected():
    """Valida que _handle_device_lost transicione a DISCONNECTED sin acumular errores."""
    from unittest.mock import AsyncMock, patch

    from core.stream_manager import StreamManager

    mgr = StreamManager()
    dp = "@device_unplugged_cam"
    proc = mgr.ensure_proc(dp)
    proc.state = State.RUNNING
    proc.is_connected = True

    async def _test():
        with patch("core.stream_manager.get_directshow_devices", new=AsyncMock(return_value=[])):
            with patch.object(mgr, "stop_stream", new=AsyncMock()):
                await mgr._handle_device_lost(dp)
                assert proc.is_connected is False
                assert proc.state == State.DISCONNECTED
                assert proc.error_count == 0
                assert proc.manual_intervention_required is False

    asyncio.run(_test())
