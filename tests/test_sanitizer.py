# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de sanitización de credenciales y registros del sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de sanitización de credenciales y registros del sistema."""

from core.ffmpeg_mgr import StreamProc
from core.sanitizer import sanitize_command_for_log, sanitize_log_line


def test_sanitize_command_srt_passphrase():
    """Valida que una contraseña compleja en URL SRT sea enmascarada en la línea de comando."""
    secret = "SUPER_SECRETO_RTMS_123456"
    cmd = [
        "ffmpeg.exe",
        "-i",
        "video=HD Webcam",
        "-f",
        "mpegts",
        f"srt://0.0.0.0:9000?mode=listener&latency=120000&passphrase={secret}&tlpktdrop=1",
    ]
    sanitized = sanitize_command_for_log(cmd)

    # El secreto real NUNCA debe aparecer
    assert secret not in sanitized
    assert "passphrase=********" in sanitized


def test_sanitize_log_line():
    """Valida que mensajes de error o logs de FFmpeg enmascaren contraseñas y tokens."""
    secret = "CLAVE_PRIVADA_987"
    raw_log = f"Failed to authenticate with peer using passphrase={secret} on socket 42"
    clean = sanitize_log_line(raw_log)

    assert secret not in clean
    assert "passphrase=********" in clean


def test_proc_memory_logs_do_not_contain_secret():
    """Valida que el buffer de logs en memoria de StreamProc aplique la sanitización."""
    secret = "SECRET_KEY_STREAM_ABC"
    proc = StreamProc("dummy_device")
    proc.log(f"Iniciando flujo con srt://127.0.0.1:9000?passphrase={secret}")

    logs = proc.get_logs()
    assert len(logs) == 1
    log_line = logs[0]
    assert secret not in log_line
    assert "passphrase=********" in log_line
