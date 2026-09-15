# ==============================================================================
# RTMS v2.2.2 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any, Union

class AutostartToggle(BaseModel):
    enable: bool

class CameraAutostartToggle(BaseModel):
    device_path: str
    auto_start: bool

class StreamAction(BaseModel):
    device_path: str
    action: Literal["start", "stop", "restart"]

class CameraConfigUpdate(BaseModel):
    device_path: str
    resolution: Literal["480p", "720p", "1080p", "1440p", "4K"] = "720p"
    fps: int = Field(default=30, ge=1, le=120)
    bitrate: int = Field(default=3000, ge=500, le=100000)
    protocol: Optional[Literal["srt", "udp"]] = "srt"
    encoder: Optional[Literal["auto", "h264_nvenc", "h264_qsv", "h264_amf", "libx264"]] = "auto"
    srt_latency: Optional[int] = Field(default=120, ge=10, le=5000)
    srt_passphrase: Optional[str] = ""
    auto_start: Optional[bool] = True
    zerolatency: Optional[bool] = True
    is_virtual: Optional[bool] = False

    @field_validator("srt_passphrase")
    @classmethod
    def validate_passphrase_length(cls, v: Optional[str]) -> Optional[str]:
        """Valida que la passphrase SRT cumpla con los requisitos del protocolo (10-79 chars) si no está vacía ni enmascarada."""
        if v and v != "••••••••" and not (10 <= len(v) <= 79):
            raise ValueError("La passphrase SRT debe tener entre 10 y 79 caracteres según el estándar del protocolo.")
        return v

class ApplyPresetRequest(BaseModel):
    device_path: str
    preset_key: str

class FullExportRequest(BaseModel):
    confirm_export_secrets: bool

class PreviewTicketRequest(BaseModel):
    device_path: str

class CameraPersistedConfig(BaseModel):
    id: Optional[str] = ""
    friendly_name: str
    device_path: str
    port: int = Field(default=9000, ge=1024, le=65535)
    resolution: Literal["480p", "720p", "1080p", "1440p", "4K"] = "720p"
    fps: int = Field(default=30, ge=1, le=120)
    bitrate: int = Field(default=3000, ge=500, le=100000)
    protocol: Optional[Literal["srt", "udp"]] = "srt"
    encoder: Optional[Literal["auto", "h264_nvenc", "h264_qsv", "h264_amf", "libx264"]] = "auto"
    srt_latency: Optional[int] = Field(default=120, ge=10, le=5000)
    srt_passphrase: Optional[str] = ""
    zerolatency: Optional[bool] = True
    auto_start: Optional[bool] = True
    is_virtual: Optional[bool] = False

class RTMSConfigModel(BaseModel):
    version: Optional[Union[str, int]] = None
    config_schema_version: Optional[int] = Field(default=3, ge=1)
    cameras: Dict[str, Union[CameraPersistedConfig, Dict[str, Any]]] = Field(default_factory=dict)
    next_port: Optional[int] = Field(default=9000, ge=1024, le=65535)
    unattended_autostart: Optional[bool] = True

class ImportConfigRequest(BaseModel):
    config_data: Dict[str, Any]

    @field_validator("config_data")
    @classmethod
    def validate_config_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Valida semánticamente que los datos de configuración contengan una estructura válida (P1-02)."""
        if not isinstance(v, dict):
            raise ValueError("El cuerpo de la configuración debe ser un objeto JSON/diccionario.")
        if "cameras" not in v or not isinstance(v["cameras"], dict):
            raise ValueError("La configuración debe contener un diccionario 'cameras'.")
        # Validación semántica Pydantic
        try:
            RTMSConfigModel.model_validate(v)
        except Exception as err:
            raise ValueError(f"Configuración inválida o campos fuera de rango: {err}") from err
        return v
