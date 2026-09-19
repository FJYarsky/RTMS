# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del servidor API en modo sin interfaz gráfica.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas del servidor API en modo sin interfaz gráfica."""

import sys
import uvicorn
from main import _NullWriter, create_app, get_free_port

def test_null_writer_interface():
    """Valida que _NullWriter implemente la interfaz básica de un stream writer."""
    writer = _NullWriter()
    assert writer.isatty() is False
    assert writer.write("test message") == len("test message")
    writer.flush()

def test_uvicorn_config_with_none_streams():
    """Valida que uvicorn.Config no falle al inicializarse cuando stdout/stderr son None."""
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = None
        sys.stderr = None

        app = create_app()
        # Con log_config=None, uvicorn no debe llamar a sys.stdout.isatty()
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_config=None)
        server = uvicorn.Server(config)
        assert server.config.log_config is None
    finally:
        sys.stdout, sys.stderr = orig_stdout, orig_stderr

def test_get_free_port_returns_valid_port():
    """Valida que get_free_port retorne un puerto entero en rango válido."""
    port = get_free_port(start_port=8100, end_port=8150)
    assert isinstance(port, int)
    assert 8100 <= port <= 8150
