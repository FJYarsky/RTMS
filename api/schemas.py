# ==============================================================================
# RTMS — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

from pydantic import BaseModel, Field
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

class ApplyPresetRequest(BaseModel):
    device_path: str
    preset_key: str

class ImportConfigRequest(BaseModel):
    config_data: Dict[str, Any]
