# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del generador de comandos de transmisión FFmpeg.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas del generador de comandos de transmisión FFmpeg."""

import asyncio

from core.stream_manager import StreamManager


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
            "zerolatency": True,
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
            "zerolatency": False,
        }
        cmd, url, enc = await mgr.build_command(cfg, force_cpu=True)

        # En broadcast/estándar no se fuerza muxdelay 0
        assert "-muxdelay" not in cmd
        assert "-flush_packets" not in cmd
        assert "tlpktdrop=0" in url

    asyncio.run(_run())


def test_build_command_url_escapes_passphrase_special_characters():
    """Valida que caracteres especiales (&, #, =, ?) en la contraseña se escapen en URLs de cliente y se aíslen del publisher loopback."""

    async def _run():
        from core.stream_proc import build_stream_url

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
            "zerolatency": True,
        }
        cmd, url, enc = await mgr.build_command(cfg, force_cpu=True)

        # En la arquitectura desacoplada v2.5.0, el comando FFmpeg hacia loopback no incluye passphrase (evita BADSECRET)
        raw_url = cmd[-1]
        assert raw_url.startswith("srt://127.0.0.1:")
        assert "streamid=publish:cam_9004" in raw_url
        assert "passphrase=" not in raw_url

        # En la URL de conexión para clientes externos (OBS), los caracteres especiales están debidamente codificados
        client_url = build_stream_url(
            protocol="srt",
            port=8890,
            passphrase=passphrase_with_symbols,
            mode="caller",
            streamid="read:cam_9004",
        )
        assert "mi_clave" in client_url
        assert "streamid=read:cam_9004" in client_url

    asyncio.run(_run())


def test_build_command_without_local_binary(monkeypatch):
    """Valida que build_command pueda construir los parámetros incluso si bin/ffmpeg.exe no existe en disco (entorno CI)."""

    async def _run():
        # Parchear solo la referencia dentro de core.hardware (NO el singleton global os.path)
        monkeypatch.setattr("core.hardware.os.path.exists", lambda p: False)
        monkeypatch.setattr("core.hardware.shutil.which", lambda cmd: None)

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
            "zerolatency": True,
        }
        cmd, url, enc = await mgr.build_command(cfg)
        assert "-tune" in cmd and "zerolatency" in cmd
        assert enc == "libx264"

    asyncio.run(_run())
