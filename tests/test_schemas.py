# ==============================================================================
# RTMS v2.2.2 — Tests de Validación de Esquemas Pydantic (api/schemas.py)
# ==============================================================================

import pytest
from pydantic import ValidationError
from api.schemas import (
    CameraConfigUpdate,
    StreamAction,
    AutostartToggle,
    CameraAutostartToggle,
    ApplyPresetRequest,
    ImportConfigRequest
)

def test_camera_config_update_valid():
    """Valida que una configuración con parámetros dentro de rango sea válida."""
    cfg = CameraConfigUpdate(
        device_path="@device_test",
        resolution="1080p",
        fps=60,
        bitrate=5000,
        protocol="srt",
        encoder="auto",
        srt_latency=120,
        srt_passphrase="passphrase_valida_123",
        auto_start=True,
        zerolatency=True
    )
    assert cfg.resolution == "1080p"
    assert cfg.fps == 60
    assert cfg.srt_passphrase == "passphrase_valida_123"

def test_camera_config_update_passphrase_empty_and_masked_are_allowed():
    """Valida que passphrases vacías o enmascaradas '••••••••' no sean rechazadas por longitud."""
    cfg_empty = CameraConfigUpdate(device_path="@test", srt_passphrase="")
    assert cfg_empty.srt_passphrase == ""

    cfg_masked = CameraConfigUpdate(device_path="@test", srt_passphrase="••••••••")
    assert cfg_masked.srt_passphrase == "••••••••"

def test_camera_config_update_passphrase_too_short():
    """Valida que passphrases menores a 10 caracteres sean rechazadas según estándar SRT."""
    with pytest.raises(ValidationError) as exc:
        CameraConfigUpdate(device_path="@test", srt_passphrase="corta")
    assert "entre 10 y 79 caracteres" in str(exc.value)

def test_camera_config_update_passphrase_too_long():
    """Valida que passphrases mayores a 79 caracteres sean rechazadas según estándar SRT."""
    with pytest.raises(ValidationError) as exc:
        CameraConfigUpdate(device_path="@test", srt_passphrase="A" * 80)
    assert "entre 10 y 79 caracteres" in str(exc.value)

def test_camera_config_update_invalid_resolution():
    """Valida que resoluciones no permitidas sean rechazadas."""
    with pytest.raises(ValidationError):
        CameraConfigUpdate(device_path="@test", resolution="999p")

def test_camera_config_update_invalid_fps_and_bitrate():
    """Valida los límites numéricos de FPS y Bitrate."""
    with pytest.raises(ValidationError):
        CameraConfigUpdate(device_path="@test", fps=0)
    with pytest.raises(ValidationError):
        CameraConfigUpdate(device_path="@test", fps=240)
    with pytest.raises(ValidationError):
        CameraConfigUpdate(device_path="@test", bitrate=100)
    with pytest.raises(ValidationError):
        CameraConfigUpdate(device_path="@test", bitrate=999999)

def test_stream_action_valid_and_invalid():
    """Valida las acciones de stream permitidas."""
    for act in ["start", "stop", "restart"]:
        obj = StreamAction(device_path="@test", action=act)
        assert obj.action == act

    with pytest.raises(ValidationError):
        StreamAction(device_path="@test", action="pause")

def test_other_schemas():
    """Valida los modelos auxiliares."""
    at = AutostartToggle(enable=True)
    assert at.enable is True

    cat = CameraAutostartToggle(device_path="@test", auto_start=False)
    assert cat.auto_start is False

    apr = ApplyPresetRequest(device_path="@test", preset_key="best")
    assert apr.preset_key == "best"

    ic = ImportConfigRequest(config_data={"version": 3, "cameras": {}})
    assert ic.config_data["version"] == 3

def test_import_config_request_validation():
    """Valida que ImportConfigRequest exija un diccionario con estructura 'cameras'."""
    # Válido
    req = ImportConfigRequest(config_data={"version": 3, "cameras": {}})
    assert req.config_data["version"] == 3

    # Inválido: falta clave cameras
    with pytest.raises(ValidationError):
        ImportConfigRequest(config_data={"version": 3})

    # Inválido: cameras no es diccionario
    with pytest.raises(ValidationError):
        ImportConfigRequest(config_data={"version": 3, "cameras": "not_a_dict"})

    # Inválido: payload completo no es diccionario
    with pytest.raises(ValidationError):
        ImportConfigRequest(config_data="invalido")
