# ==============================================================================
# RTMS — Real-Time Multicam System
# Tests E2E de Cadena de Ejecución, Diagnóstico y Medición de Ping
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas automatizadas E2E para el verificador de cadena de ejecución y benchmark de ping."""

import os
import subprocess
import sys
import time

import pytest
from PIL import Image, ImageDraw

from core.mediamtx_mgr import mediamtx_manager
from core.pipeline_verifier import (
    BENCH_FPS,
    BENCH_HEIGHT,
    BENCH_WIDTH,
    CorePipelineVerifier,
    SyntheticClockGenerator,
    _decode_bits,
    _encode_bits,
    decode_burned_in_header,
    draw_burned_in_header,
)

# ---------------------------------------------------------------------------
# Condiciones de entorno para skip de pruebas que requieren binarios locales
# y subprocesos con acceso a hardware real (no aplicable en CI headless).
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
_HAS_MEDIAMTX = os.path.exists(os.path.join(_REPO_ROOT, "bin", "mediamtx.exe"))
_HAS_FFMPEG_BIN = os.path.exists(os.path.join(_REPO_ROOT, "bin", "ffmpeg.exe"))
_IS_CI = os.environ.get("GITHUB_ACTIONS") == "true"
_CAN_RUN_E2E = _HAS_MEDIAMTX and _HAS_FFMPEG_BIN and not _IS_CI


def test_bit_encoding_decoding():
    """Valida la codificación y decodificación binaria de enteros sin pérdida."""
    for val in [0, 1, 42, 1024, 16777215, 281474976710655]:
        bits = _encode_bits(val, 48)
        assert len(bits) == 48
        decoded = _decode_bits(bits)
        assert decoded == val

    for val in [0, 1, 255, 65535]:
        bits = _encode_bits(val, 16)
        assert len(bits) == 16
        decoded = _decode_bits(bits)
        assert decoded == val


def test_optical_barcode_burned_in_header():
    """Valida el dibujado óptico de código de barras y su posterior decodificación en memoria."""
    img = Image.new("RGB", (BENCH_WIDTH, BENCH_HEIGHT), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    timestamp_ms = int(time.time() * 1000)
    frame_idx = 1337

    draw_burned_in_header(draw, timestamp_ms, frame_idx)
    raw_bytes = img.tobytes()

    res = decode_burned_in_header(raw_bytes, BENCH_WIDTH, BENCH_HEIGHT)
    assert res is not None, "El código de barras óptico no pudo ser decodificado"
    dec_ts, dec_idx = res
    assert dec_ts == timestamp_ms, f"Timestamp esperado {timestamp_ms}, decodificado {dec_ts}"
    assert dec_idx == frame_idx, f"Frame idx esperado {frame_idx}, decodificado {dec_idx}"


def test_optical_barcode_corruption_rejection():
    """Valida que un cuadro con ruido o código de barras alterado sea rechazado como corrupto (None)."""
    corrupt_bytes = bytes([0] * (BENCH_WIDTH * BENCH_HEIGHT * 3))
    res = decode_burned_in_header(corrupt_bytes, BENCH_WIDTH, BENCH_HEIGHT)
    assert res is None, "Un cuadro negro sin preámbulo Barker debió retornar None"

    incomplete_bytes = b"demasiado_corto"
    res_incomplete = decode_burned_in_header(incomplete_bytes, BENCH_WIDTH, BENCH_HEIGHT)
    assert res_incomplete is None


def test_synthetic_clock_generator_rendering():
    """Valida la generación de cuadros sintéticos completos y legibilidad de cabecera."""
    gen = SyntheticClockGenerator(width=BENCH_WIDTH, height=BENCH_HEIGHT, fps=BENCH_FPS)
    now_ms = int(time.time() * 1000)
    raw_frame = gen.render_frame(frame_idx=10, timestamp_ms=now_ms)

    assert len(raw_frame) == BENCH_WIDTH * BENCH_HEIGHT * 3
    res = decode_burned_in_header(raw_frame, BENCH_WIDTH, BENCH_HEIGHT)
    assert res is not None
    dec_ts, dec_idx = res
    assert dec_ts == now_ms
    assert dec_idx == 10


def test_cli_tester_help_and_dry_run():
    """Valida que el script CLI e2e_pipeline_tester.py responda adecuadamente al argumento --help."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "e2e_pipeline_tester.py")
    res = subprocess.run([sys.executable, script_path, "--help"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "--all" in res.stdout
    assert "--ping" in res.stdout
    assert "--obs-mode" in res.stdout


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _CAN_RUN_E2E,
    reason="Requiere bin/mediamtx.exe y bin/ffmpeg.exe fuera de entorno CI (GITHUB_ACTIONS=true).",
)
async def test_pipeline_verifier_srt_end_to_end():
    """Prueba E2E real: genera stream virtual de reloj, publica en MediaMTX vía SRT y verifica recepción."""
    verifier = CorePipelineVerifier()
    try:
        res = await verifier.verify_srt_unencrypted()
        assert res.status == "PASS", f"La prueba de SRT sin cifrar falló: {res.details} | error={res.error}"
    finally:
        mediamtx_manager.stop()
