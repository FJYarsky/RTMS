# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de configuración del inicio automático en Windows.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de configuración del inicio automático en Windows."""

from core.autostart import enable_autostart, get_launch_command, get_startup_path, is_autostart_enabled


def test_get_startup_path_structure():
    """Valida que la ruta de inicio apunte a un archivo .cmd dentro del Start Menu de Windows."""
    path = get_startup_path()
    assert str(path).endswith("rtms_startup.cmd")
    assert "Startup" in str(path) or "Inicio" in str(path)


def test_get_launch_command_content():
    """Valida que el comando de lanzamiento contenga invocación desacoplada con start."""
    workdir, cmd = get_launch_command()
    assert len(workdir) > 0
    assert 'start ""' in cmd


def test_enable_and_disable_autostart_isolated(tmp_path, monkeypatch):
    """Valida la creación, lectura y eliminación del archivo de autoarranque en un directorio aislado."""
    mock_batch = tmp_path / "Startup" / "rtms_startup.cmd"
    monkeypatch.setattr("core.autostart.get_startup_path", lambda: mock_batch)

    # Estado inicial: no habilitado
    assert is_autostart_enabled() is False

    # Habilitar autoarranque
    enable_autostart(True)
    assert is_autostart_enabled() is True
    assert mock_batch.is_file()

    # Validar contenido del script batch generado
    content = mock_batch.read_text(encoding="utf-8")
    assert "@echo off" in content
    assert 'start ""' in content
    assert "exit" in content

    # Deshabilitar autoarranque
    enable_autostart(False)
    assert is_autostart_enabled() is False
    assert not mock_batch.exists()
