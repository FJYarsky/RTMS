# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.2
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

from pydantic import BaseModel
from typing import Optional

class AutostartToggle(BaseModel):
    enable: bool

class CameraAutostartToggle(BaseModel):
    device_path: str
    auto_start: bool

class StreamAction(BaseModel):
    device_path: str
    action: str  # "start", "stop", "restart"

class CameraConfigUpdate(BaseModel):
    device_path: str
    resolution: str
    fps: int
    bitrate: int
    protocol: Optional[str] = "srt"
    encoder: Optional[str] = "auto"
    srt_latency: Optional[int] = 120
    srt_passphrase: Optional[str] = ""
    auto_start: Optional[bool] = True
    zerolatency: Optional[bool] = True
    is_virtual: Optional[bool] = False
