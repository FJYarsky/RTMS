# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de gestión y validación de configuraciones.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de gestión y validación de configuraciones."""

from core.config_mgr import get_or_allocate_camera_config, import_config, is_virtual_device, load_config


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


def test_import_config_valid():
    """Valida la importación exitosa de un diccionario de configuración válido."""
    valid_payload = {
        "version": "2.3.0",
        "config_schema_version": 4,
        "cameras": {
            "@cam1": {
                "id": "cam_abc123",
                "device_path": "@cam1",
                "friendly_name": "Camera 1",
                "port": 9000,
                "protocol": "srt",
            }
        },
    }
    assert import_config(valid_payload) is True
    loaded = load_config()
    assert "@cam1" in loaded.get("cameras", {})


def test_import_config_invalid_payloads():
    """Valida que payloads con tipos erróneos o sin formato de cámaras sean rechazados de forma segura."""
    assert import_config("cadena_invalida") is False
    assert import_config(None) is False
    assert import_config([1, 2, 3]) is False
    assert import_config({"version": "2.2.2"}) is False
    assert import_config({"cameras": "no_es_dict"}) is False
    assert import_config({"cameras": [1, 2, 3]}) is False
    assert import_config({"cameras": {"@cam1": "string_invalida"}}) is False
