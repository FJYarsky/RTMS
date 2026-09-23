# ==============================================================================
# RTMS — Real-Time Multicam System
# Modelos Pydantic v2 de Dominio Estricto para Configuración.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Modelos Pydantic v2 para validación estricta de configuraciones de cámaras y sistema."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CameraConfig(BaseModel):
    """Modelo estricto de dominio para configuración individual de cámaras."""

    id: Optional[str] = ""
    friendly_name: str
    device_path: str
    port: int = Field(default=9000, ge=1024, le=65535)
    resolution: Literal["480p", "720p", "1080p", "1440p", "4K"] = "720p"
    fps: int = Field(default=30, ge=15, le=120)
    bitrate: int = Field(default=3000, ge=500, le=50000)
    protocol: Literal["srt", "udp"] = "srt"
    encoder: Literal["auto", "h264_nvenc", "h264_qsv", "h264_amf", "libx264"] = "auto"
    srt_latency: int = Field(default=120, ge=10, le=5000)
    srt_passphrase: Optional[str] = ""
    zerolatency: bool = True
    auto_start: bool = True
    is_virtual: bool = False
    udp_mode: Optional[Literal["multicast", "unicast"]] = "multicast"
    udp_host: Optional[str] = "127.0.0.1"

    @field_validator("srt_passphrase")
    @classmethod
    def validate_passphrase_length(cls, v: Optional[str]) -> Optional[str]:
        """Valida que la passphrase SRT tenga entre 10 y 79 caracteres si está presente."""
        if v and v != "••••••••" and not (10 <= len(v) <= 79):
            raise ValueError("La passphrase SRT debe tener entre 10 y 79 caracteres.")
        return v


class SystemSettingsConfig(BaseModel):
    """Modelo estricto de configuración global del sistema RTMS."""

    mediamtx_srt_port: int = Field(default=8890, ge=1024, le=65535)
    mediamtx_webrtc_port: int = Field(default=8889, ge=1024, le=65535)
    unattended_autostart: bool = False
    api_port: Optional[int] = Field(default=8000, ge=1024, le=65535)
