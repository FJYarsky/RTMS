# ==============================================================================
# RTMS v2.2.0 — Tests Deterministas de Construcción de Comandos FFmpeg
# ==============================================================================

import asyncio
from core.ffmpeg_mgr import StreamManager

def test_build_command_zerolatency_true():
    """Valida que zerolatency=True aplique los parámetros de ultra baja latencia."""
    async def _run():
        mgr = StreamManager()
        cfg = {
            "device_path": "@device_test",
            "friendly_name": "Test Cam",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "encoder": "libx264",
            "srt_latency": 100,
            "zerolatency": True
        }
        cmd, url, enc = await mgr.build_command(cfg, force_cpu=True)

        # Flags esperados en zerolatency=True
        assert "-tune" in cmd and "zerolatency" in cmd
        assert "-muxdelay" in cmd
        assert "-flush_packets" in cmd
        assert "tlpktdrop=1" in url

    asyncio.run(_run())

def test_build_command_zerolatency_false():
    """Valida que zerolatency=False genere un perfil balanceado sin forzar muxdelay 0 ni packet drop."""
    async def _run():
        mgr = StreamManager()
        cfg = {
            "device_path": "@device_test",
            "friendly_name": "Test Cam",
            "resolution": "1080p",
            "fps": 60,
            "bitrate": 6000,
            "protocol": "srt",
            "port": 9002,
            "encoder": "libx264",
            "srt_latency": 200,
            "zerolatency": False
        }
        cmd, url, enc = await mgr.build_command(cfg, force_cpu=True)

        # En broadcast/estándar no se fuerza muxdelay 0
        assert "-muxdelay" not in cmd
        assert "-flush_packets" not in cmd
        assert "tlpktdrop=0" in url

    asyncio.run(_run())

def test_build_command_url_escapes_passphrase_special_characters():
    """Valida que caracteres especiales (&, #, =, ?) en la contraseña no rompan el formato de URL SRT."""
    async def _run():
        mgr = StreamManager()
        passphrase_with_symbols = "mi_clave&foo=bar#123?ok"
        cfg = {
            "device_path": "@device_test",
            "friendly_name": "Test Cam",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9004,
            "encoder": "libx264",
            "srt_passphrase": passphrase_with_symbols,
            "zerolatency": True
        }
        cmd, url, enc = await mgr.build_command(cfg, force_cpu=True)

        # En la URL cruda debe estar codificada (ej. %26 en vez de & sin escapar)
        assert "mi_clave" in url
        # Comprobar que no hay inyección de parámetros secundarios espurios
        assert "foo=bar" not in url.split("passphrase=")[0]

    asyncio.run(_run())

def test_build_command_without_local_binary(monkeypatch):
    """Valida que build_command pueda construir los parámetros incluso si bin/ffmpeg.exe no existe en disco (entorno CI)."""
    async def _run():
        import core.hardware
        monkeypatch.setattr(core.hardware.os.path, "exists", lambda p: False)
        monkeypatch.setattr(core.hardware.shutil, "which", lambda cmd: None)

        mgr = StreamManager()
        cfg = {
            "device_path": "@device_test",
            "friendly_name": "Test Cam",
            "resolution": "720p",
            "fps": 30,
            "bitrate": 3000,
            "protocol": "srt",
            "port": 9000,
            "encoder": "auto",
            "srt_latency": 100,
            "zerolatency": True
        }
        cmd, url, enc = await mgr.build_command(cfg)
        assert "-tune" in cmd and "zerolatency" in cmd
        assert enc == "libx264"

    asyncio.run(_run())

