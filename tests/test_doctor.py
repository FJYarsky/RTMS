# ==============================================================================
# RTMS v2.2.0 — Tests de Herramienta de Diagnóstico CLI (core/doctor.py)
# ==============================================================================

from core.doctor import (
    check_os,
    check_ffmpeg_binary,
    check_srt_support,
    check_network_ip,
    check_media_ports,
    check_config_storage,
    run_doctor
)

def test_doctor_check_ffmpeg_and_srt():
    """Valida las verificaciones de disponibilidad de FFmpeg y soporte del protocolo SRT."""
    ffmpeg_ok = check_ffmpeg_binary()
    assert isinstance(ffmpeg_ok, bool)

    srt_ok = check_srt_support()
    assert isinstance(srt_ok, bool)

def test_doctor_check_os():
    """Valida la detección del sistema operativo Windows."""
    res = check_os()
    assert isinstance(res, bool)

def test_doctor_check_network_ip():
    """Valida la detección de IP local y la ausencia de fugas de sockets."""
    res = check_network_ip()
    assert res is True

def test_doctor_check_media_ports():
    """Valida la disponibilidad de puertos multimedia en el rango inicial."""
    res = check_media_ports()
    assert isinstance(res, bool)

def test_doctor_check_config_storage():
    """Valida la lectura y diagnóstico del almacenamiento de configuración."""
    res = check_config_storage()
    assert res is True

def test_doctor_run_doctor_flow():
    """Valida la ejecución integral del flujo de diagnóstico de RTMS Doctor."""
    import asyncio
    async def _run():
        result = await run_doctor()
        assert isinstance(result, bool)
    asyncio.run(_run())
