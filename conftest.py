# ==============================================================================
# RTMS — Real-Time Multicam System
# Configuración y fixtures compartidos para pruebas automatizadas.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pytest configuration, async cleanup, and test isolation fixtures."""

import sys
import os
import pytest

# Asegurar que el directorio raíz del proyecto esté siempre en sys.path durante los tests
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

@pytest.fixture(autouse=True)
def isolate_test_config(tmp_path, monkeypatch):
    """
    Aísla completamente la persistencia de configuración durante la ejecución de pruebas.
    Garantiza que ningún test pueda modificar ni contaminar el config/config.json real de producción.
    """
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir(parents=True, exist_ok=True)
    test_config_file = str(test_config_dir / "config.json")
    test_config_bak = str(test_config_dir / "config.json.bak")
    test_config_tmp = str(test_config_dir / "config.json.tmp")

    monkeypatch.setattr("core.config_mgr.CONFIG_DIR", str(test_config_dir))
    monkeypatch.setattr("core.config_mgr.CONFIG_FILE", test_config_file)
    monkeypatch.setattr("core.config_mgr.CONFIG_BAK_FILE", test_config_bak)
    monkeypatch.setattr("core.config_mgr.CONFIG_TMP_FILE", test_config_tmp)
    if hasattr(sys.modules.get("core.config_mgr"), "_LAST_SAVED_CONFIG"):
        monkeypatch.setattr("core.config_mgr._LAST_SAVED_CONFIG", None)
    yield

@pytest.fixture(autouse=True)
def cleanup_stream_manager():
    """Garantiza la cancelación limpia de tareas de watchdog asíncronas y slots de preview tras cada test."""
    yield
    from core.ffmpeg_mgr import stream_manager
    from core.preview_mgr import preview_manager
    import asyncio
    if stream_manager._watchdog_task and not stream_manager._watchdog_task.done():
        stream_manager._watchdog_task.cancel()
    stream_manager._procs.clear()
    try:
        asyncio.run(preview_manager.stop_all())
    except Exception:
        pass

