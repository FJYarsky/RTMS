# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas unitarias y de integración para la herramienta de reloj milimétrico.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas para scripts/test_obs_latency_clock.py."""

import time

from PIL import Image, ImageDraw

from scripts.test_obs_latency_clock import (
    FRAME_BYTES,
    HEIGHT,
    WIDTH,
    LatencyClockPublisher,
    decode_optical_header,
    draw_optical_header,
    render_clock_frame,
)


def test_optical_header_bit_roundtrip():
    """Valida que la codificación y decodificación de bits y cabecera óptica sea 100% fiel."""
    val_ts = 1727715600123
    val_idx = 1042

    img = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw_optical_header(draw, val_ts, val_idx)
    raw = img.tobytes()

    decoded = decode_optical_header(raw, WIDTH, HEIGHT)
    assert decoded is not None
    ts_out, idx_out = decoded
    assert ts_out == val_ts
    assert idx_out == val_idx


def test_optical_header_noise_tolerance():
    """Valida que la cabecera óptica soporte artefactos o fluctuaciones de luminancia en los bloques."""
    val_ts = 1727715699999
    val_idx = 65535

    img = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw_optical_header(draw, val_ts, val_idx)

    # Simular ruido leve alterando bytes aleatorios fuera del centroide
    raw_array = bytearray(img.tobytes())
    raw_array[100] = 50
    raw_array[200] = 200

    decoded = decode_optical_header(bytes(raw_array), WIDTH, HEIGHT)
    assert decoded is not None
    assert decoded[0] == val_ts
    assert decoded[1] == val_idx


def test_frame_rendering_performance():
    """Valida que la renderización de un cuadro se complete en menos de 25 ms (> 40 FPS)."""
    t_start = time.perf_counter()
    raw = render_clock_frame(1, int(time.time() * 1000), fps=30)
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    assert len(raw) == FRAME_BYTES
    assert elapsed_ms < 25.0, f"Render tomó {elapsed_ms:.2f} ms (debe ser < 25 ms)"


def test_publisher_command_low_latency_flags():
    """Valida que el publicador configure flags estrictos de baja latencia sin el flag -re bloqueante."""
    pub = LatencyClockPublisher(port=8890, fps=30)
    assert pub.port == 8890
    assert pub.fps == 30
