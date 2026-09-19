# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de detección y parseo de dispositivos de captura.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de detección y parseo de dispositivos de captura."""

from core.hardware import parse_dshow_output


def test_parse_dshow_modern_format():
    """Valida el análisis del formato moderno de DirectShow introducido en FFmpeg 7.x/8.x."""
    sample_output = """
ffmpeg version 7.0 Copyright (c) 2000-2024 the FFmpeg developers
[in#0 @ 000001e3b14fd300] DirectShow video devices (from video devices)
[in#0 @ 000001e3b14fd300]  "HD Webcam" (video)
[in#0 @ 000001e3b14fd300]   Alternative name "@device_pnp_\\\\?\\usb#vid_5986&pid_211b&mi_00#6&3a3d274b&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\\global"
[in#0 @ 000001e3b14fd300]  "OBS Virtual Camera" (video)
[in#0 @ 000001e3b14fd300]   Alternative name "@device_sw_{860BB310-5D01-11D0-BD3B-00A0C911CE86}\\{A3FCE0F5-3493-419F-958A-ABA92502337C}"
[in#0 @ 000001e3b14fd300] DirectShow audio devices
[in#0 @ 000001e3b14fd300]  "Microphone" (audio)
    """
    devices = parse_dshow_output(sample_output)
    assert len(devices) == 2
    assert devices[0]["friendly_name"] == "HD Webcam"
    assert "@device_pnp_" in devices[0]["device_path"]
    assert devices[1]["friendly_name"] == "OBS Virtual Camera"


def test_parse_dshow_legacy_format():
    """Valida el análisis del formato clásico de DirectShow (FFmpeg 4.x - 6.x)."""
    sample_output = """
[dshow @ 000002194203cf00] DirectShow video devices
[dshow @ 000002194203cf00]  "Integrated Camera"
[dshow @ 000002194203cf00]     Alternative name "@device_pnp_\\\\?\\usb#vid_04f2&pid_b604&mi_00#6&12345"
[dshow @ 000002194203cf00] DirectShow audio devices
    """
    devices = parse_dshow_output(sample_output)
    assert len(devices) == 1
    assert devices[0]["friendly_name"] == "Integrated Camera"
    assert "@device_pnp_" in devices[0]["device_path"]


def test_parse_dshow_empty_output():
    """Valida que una salida vacía o sin cámaras retorne lista vacía sin excepciones."""
    devices = parse_dshow_output("Dummy output with no devices")
    assert devices == []
