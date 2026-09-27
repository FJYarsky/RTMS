# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de concurrencia de hardware, deduplicación single-flight y manejo Proactor.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Pruebas exhaustivas para la auditoría de concurrencia y sondeo de hardware:
- Deduplicación y coalescing (single-flight) en DirectShowDeviceScanner
- Comportamiento de caché con TTL corto (4 segundos) y refresco forzado
- Manejador de excepciones ProactorEventLoop en Windows (WinError 10054)
- Exclusión mutua de sincronización de hardware en StreamManager
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hardware import DirectShowDeviceScanner, dshow_scanner, get_directshow_devices
from main import (
    install_proactor_loop_exception_handler,
    patch_proactor_connection_lost,
    proactor_exception_handler,
)


@pytest.fixture(autouse=True)
def reset_scanner_state():
    """Garantiza aislamiento limpio del escáner antes y después de cada prueba."""
    dshow_scanner.reset()
    yield
    dshow_scanner.reset()


@pytest.mark.asyncio
async def test_dshow_scanner_single_flight_coalescing():
    """Valida que múltiples llamadas concurrentes simultáneas ejecuten un único subproceso FFmpeg."""
    scanner = DirectShowDeviceScanner(cache_ttl=4.0)
    probe_call_count = 0

    async def mock_execute_probe():
        nonlocal probe_call_count
        probe_call_count += 1
        await asyncio.sleep(0.05)  # Simular latencia de comunicación de FFmpeg
        return [{"friendly_name": "USB Cam 1", "device_path": "@device_pnp_cam1"}]

    with patch.object(scanner, "_execute_probe", side_effect=mock_execute_probe):
        # 5 llamadas concurrentes al mismo milisegundo
        results = await asyncio.gather(
            scanner.get_devices(),
            scanner.get_devices(),
            scanner.get_devices(),
            scanner.get_devices(),
            scanner.get_devices(),
        )

        # Debe haberse ejecutado exactamente 1 vez (single-flight / coalescing)
        assert probe_call_count == 1
        assert len(results) == 5
        for r in results:
            assert len(r) == 1
            assert r[0]["friendly_name"] == "USB Cam 1"


@pytest.mark.asyncio
async def test_dshow_scanner_ttl_cache():
    """Valida que las llamadas posteriores dentro de la ventana TTL usen la memoria caché sin reejecutar FFmpeg."""
    scanner = DirectShowDeviceScanner(cache_ttl=4.0)
    probe_call_count = 0

    async def mock_execute_probe():
        nonlocal probe_call_count
        probe_call_count += 1
        return [{"friendly_name": "Integrated Cam", "device_path": "@device_pnp_int"}]

    with patch.object(scanner, "_execute_probe", side_effect=mock_execute_probe):
        # 1. Primera llamada: sondeo real
        res1 = await scanner.get_devices()
        assert probe_call_count == 1
        assert len(res1) == 1

        # 2. Segunda llamada inmediata: debe responder desde caché sin re-sondear
        res2 = await scanner.get_devices()
        assert probe_call_count == 1
        assert res2 == res1

        # 3. Llamada con force_refresh=True: debe invalidar la caché y re-sondear
        res3 = await scanner.get_devices(force_refresh=True)
        assert probe_call_count == 2
        assert res3 == res1


@pytest.mark.asyncio
async def test_dshow_scanner_invalidate_cache():
    """Valida que invalidate_cache limpie la caché para el siguiente sondeo."""
    scanner = DirectShowDeviceScanner(cache_ttl=4.0)
    probe_call_count = 0

    async def mock_execute_probe():
        nonlocal probe_call_count
        probe_call_count += 1
        return [{"friendly_name": "Test Cam", "device_path": "@device_test"}]

    with patch.object(scanner, "_execute_probe", side_effect=mock_execute_probe):
        await scanner.get_devices()
        assert probe_call_count == 1

        scanner.invalidate_cache()
        await scanner.get_devices()
        assert probe_call_count == 2


@pytest.mark.asyncio
async def test_dshow_scanner_graceful_fallback_on_error():
    """Valida la degradación grácil ante excepciones durante el sondeo sin bloquear llamadas futuras."""
    scanner = DirectShowDeviceScanner(cache_ttl=4.0)
    should_fail = True

    async def mock_execute_probe():
        if should_fail:
            raise RuntimeError("FFmpeg process crashed")
        return [{"friendly_name": "Recovered Cam", "device_path": "@device_rec"}]

    with patch.object(scanner, "_execute_probe", side_effect=mock_execute_probe):
        # Primera llamada falla: debe capturar error y retornar lista vacía
        res1 = await scanner.get_devices()
        assert res1 == []
        assert scanner._inflight_task is None

        # Llamada posterior cuando FFmpeg vuelve a responder: debe funcionar
        should_fail = False
        res2 = await scanner.get_devices()
        assert len(res2) == 1
        assert res2[0]["friendly_name"] == "Recovered Cam"


@pytest.mark.asyncio
async def test_get_directshow_devices_global_function():
    """Valida la función pública get_directshow_devices delegando en el singleton dshow_scanner."""
    with patch.object(
        dshow_scanner, "get_devices", new=AsyncMock(return_value=[{"friendly_name": "CamA", "device_path": "dpA"}])
    ) as mock_get:
        res = await get_directshow_devices(force_refresh=True)
        mock_get.assert_called_once_with(force_refresh=True)
        assert len(res) == 1


def test_proactor_exception_handler_silences_winerror_10054():
    """Valida que ConnectionResetError [WinError 10054] sea silenciado sin invocar default_exception_handler."""
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    err_10054 = ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host")

    context = {
        "message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost",
        "exception": err_10054,
    }

    proactor_exception_handler(mock_loop, context)
    mock_loop.default_exception_handler.assert_not_called()


def test_proactor_exception_handler_silences_oserror_10054():
    """Valida que OSError con winerror=10054 sea silenciado."""
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    err = OSError(10054, "WSAECONNRESET")
    err.winerror = 10054

    context = {
        "message": "Fatal error on pipe transport",
        "exception": err,
    }

    proactor_exception_handler(mock_loop, context)
    mock_loop.default_exception_handler.assert_not_called()


def test_proactor_exception_handler_delegates_unrelated_exceptions():
    """Valida que excepciones no relacionadas sean delegadas a default_exception_handler."""
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    unrelated_err = ValueError("Unexpected computation failure")

    context = {
        "message": "Task crashed",
        "exception": unrelated_err,
    }

    proactor_exception_handler(mock_loop, context)
    mock_loop.default_exception_handler.assert_called_once_with(context)


def test_install_proactor_loop_exception_handler():
    """Valida la instalación del handler en el bucle provisto."""
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    install_proactor_loop_exception_handler(mock_loop)
    mock_loop.set_exception_handler.assert_called_once_with(proactor_exception_handler)


def test_patch_proactor_connection_lost_execution():
    """Valida que el parche defensivo se instale sin errores en Windows."""
    patch_proactor_connection_lost()


@pytest.mark.asyncio
async def test_stream_manager_sync_streams_lock():
    """Valida que sync_streams_with_hardware garantice exclusión mutua para evitar carreras de sondeo."""
    from core.stream_manager import StreamManager

    sm = StreamManager()
    sync_executions = 0

    async def fake_get_devices(force_refresh=False):
        nonlocal sync_executions
        sync_executions += 1
        await asyncio.sleep(0.02)
        return []

    with patch("core.stream_manager.get_directshow_devices", side_effect=fake_get_devices):
        # Lanzar 3 sincronizaciones de hardware concurrentes
        await asyncio.gather(
            sm.sync_streams_with_hardware(),
            sm.sync_streams_with_hardware(),
            sm.sync_streams_with_hardware(),
        )

        # Las tres deben completarse limpiamente
        assert sync_executions == 3
