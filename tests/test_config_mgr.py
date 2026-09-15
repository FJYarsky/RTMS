# ==============================================================================
# RTMS v2.1.0 — Tests Unitarios para Configuración (core/config_mgr.py)
# ==============================================================================

from core.config_mgr import is_virtual_device, get_or_allocate_camera_config

def test_is_virtual_device_detection():
    """Valida la detección heurística de dispositivos de software/virtuales."""
    assert is_virtual_device("OBS Virtual Camera") is True
    assert is_virtual_device("Elgato Virtual Camera") is True
    assert is_virtual_device("vMix Video") is True
    assert is_virtual_device("Unity Video Capture") is True
    assert is_virtual_device("DroidCam Source") is True
    assert is_virtual_device("Iriun Webcam") is True

    # Cámaras físicas no deben ser detectadas como virtuales
    assert is_virtual_device("HD Webcam") is False
    assert is_virtual_device("Logitech Brio 4K") is False
    assert is_virtual_device("Sony A6400 (Cam Link 4K)") is False
    assert is_virtual_device("Integrated Camera") is False

def test_get_or_allocate_camera_config():
    """Valida asignación de puerto, protocolo SRT y generación de contraseña segura."""
    device_path = "@device_test_cam_123"
    friendly_name = "Camara de Estudio"
    cfg = get_or_allocate_camera_config(device_path, friendly_name)

    assert cfg["friendly_name"] == friendly_name
    assert cfg["protocol"] == "srt"
    assert cfg["port"] >= 9000
    assert len(cfg["srt_passphrase"]) >= 10  # Cumple requerimiento mínimo de longitud de SRT
    assert cfg["auto_start"] is True
    assert cfg["zerolatency"] is True
    assert cfg["is_virtual"] is False
