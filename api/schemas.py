# ==============================================================================
# RTMS v2.2.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any

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

class ImportConfigRequest(BaseModel):
    config_data: Dict[str, Any]
