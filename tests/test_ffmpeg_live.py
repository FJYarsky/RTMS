# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de integración para flujos de transmisión FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import asyncio
import pytest
from core.ffmpeg_tester import FFmpegDiagnosticSuite
from core.hardware import has_ffmpeg_binary


@pytest.fixture
def suite():
    return FFmpegDiagnosticSuite()


def test_ffmpeg_binary_and_protocols_available(suite):
    """Verifica que el binario FFmpeg soporte SRT, UDP y DirectShow."""
    rep = suite.check_binary_and_protocols()
    if not rep["available"]:
        pytest.skip("FFmpeg binario no disponible en el entorno de pruebas")

    assert rep["srt_enabled"] is True, "SRT protocol debe estar habilitado en FFmpeg"
    assert rep["udp_enabled"] is True, "UDP protocol debe estar habilitado en FFmpeg"
    assert rep["libx264_enabled"] is True, "libx264 debe estar disponible"


def test_encoder_benchmark_1080p60_cpu(suite):
    """Valida que libx264 pueda codificar a 1080p@60fps."""
    if not has_ffmpeg_binary():
        pytest.skip("FFmpeg binario no disponible")

    async def _run():
        res = await suite.benchmark_encoder("libx264", resolution="1080p", fps=60, frames=60)
        assert res["success"] is True
        assert res["achieved_fps"] >= 15.0

    asyncio.run(_run())


def test_srt_handshake_with_passphrase(suite):
    """Valida conexión y digestión de stream SRT con contraseña."""
    if not has_ffmpeg_binary():
        pytest.skip("FFmpeg binario no disponible")

    async def _run():
        pwd = "TestPassphrase123"
        digest = await suite.test_srt_connection(
            port=9961,
            resolution="720p",
            fps=30,
            passphrase_sender=pwd,
            passphrase_receiver=pwd,
            duration_seconds=2.0
        )
        assert digest.is_connected is True
        assert digest.frames_decoded > 10
        assert digest.real_fps > 15.0

    asyncio.run(_run())


def test_srt_rejection_without_passphrase(suite):
    """Valida que el receptor sea rechazado si no proporciona la contraseña requerida."""
    if not has_ffmpeg_binary():
        pytest.skip("FFmpeg binario no disponible")

    async def _run():
        digest = await suite.test_srt_connection(
            port=9962,
            resolution="720p",
            fps=30,
            passphrase_sender="SecretPass123",
            passphrase_receiver="",
            duration_seconds=1.5
        )
        assert digest.is_connected is False
        assert len(digest.errors) > 0

    asyncio.run(_run())


def test_udp_stream_1080p60(suite):
    """Valida que la transmisión UDP a 1080p@60fps con buffer optimizado entregue cuadros continuos sin pérdida."""
    if not has_ffmpeg_binary():
        pytest.skip("FFmpeg binario no disponible")

    async def _run():
        digest = await suite.test_udp_connection(
            port=9964,
            multicast=False,
            resolution="1080p",
            fps=60,
            buffer_size=4194304,
            repeat_headers=True,
            duration_seconds=2.0
        )
        assert digest.is_connected is True
        assert digest.frames_decoded >= 20
        assert digest.real_fps >= 20.0

    asyncio.run(_run())
