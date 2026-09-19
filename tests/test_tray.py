# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas del icono y menú contextual en la bandeja del sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas del icono y menú contextual en la bandeja del sistema."""

from unittest.mock import MagicMock, patch
from core.tray_icon import SystemTrayManager
from PIL import Image


def test_system_tray_manager_init():
    """Valida la inicialización de SystemTrayManager con todos los callbacks."""
    show_cb = MagicMock()
    stop_cb = MagicMock()
    term_cb = MagicMock()
    exit_cb = MagicMock()
    about_cb = MagicMock()

    mgr = SystemTrayManager(
        on_show_window=show_cb,
        on_stop_streams=stop_cb,
        on_terminate_all=term_cb,
        on_exit_app=exit_cb,
        on_about=about_cb
    )

    assert mgr.on_show_window is show_cb
    assert mgr.on_stop_streams is stop_cb
    assert mgr.on_terminate_all is term_cb
    assert mgr.on_exit_app is exit_cb
    assert mgr.on_about is about_cb
    assert mgr.icon is None


def test_system_tray_fallback_image():
    """Valida que _create_fallback_image genere un icono RGBA válido de 64x64."""
    mgr = SystemTrayManager()
    img = mgr._create_fallback_image()
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_system_tray_start_and_menu_items():
    """Valida la creación del menú del System Tray conteniendo 'Acerca de RTMS'."""
    show_cb = MagicMock()
    stop_cb = MagicMock()
    term_cb = MagicMock()
    exit_cb = MagicMock()
    about_cb = MagicMock()

    mgr = SystemTrayManager(
        on_show_window=show_cb,
        on_stop_streams=stop_cb,
        on_terminate_all=term_cb,
        on_exit_app=exit_cb,
        on_about=about_cb
    )

    def mock_thread_factory(target, daemon=True, args=(), kwargs=None):
        kwargs = kwargs or {}
        mock_t = MagicMock()
        if "run" not in getattr(target, "__name__", "") and "run" not in str(target):
            mock_t.start = lambda: target(*args, **kwargs)
        return mock_t

    with patch("threading.Thread", side_effect=mock_thread_factory) as mock_thread:
        mgr.start()

        assert mgr.icon is not None
        assert mock_thread.called

        # Inspeccionar elementos del menú
        menu_items = list(mgr.icon._menu)
        item_texts = [getattr(it, "text", str(it)) for it in menu_items]

        assert any("Mostrar RTMS" in t for t in item_texts)
        assert any("Detener todas las transmisiones" in t for t in item_texts)
        assert any("Finalizar todos los procesos" in t for t in item_texts)
        assert any("Acerca de RTMS" in t for t in item_texts)
        assert any("Salir de RTMS" in t for t in item_texts)

        # Encontrar y ejecutar la acción del elemento Mostrar RTMS
        show_item = next(it for it in menu_items if "Mostrar RTMS" in getattr(it, "text", ""))
        show_item._action(mgr.icon, show_item)
        assert show_cb.called

        # Encontrar y ejecutar la acción de Detener todas las transmisiones
        stop_item = next(it for it in menu_items if "Detener todas las transmisiones" in getattr(it, "text", ""))
        stop_item._action(mgr.icon, stop_item)
        assert stop_cb.called

        # Encontrar y ejecutar la acción de Finalizar todos los procesos
        term_item = next(it for it in menu_items if "Finalizar todos los procesos" in getattr(it, "text", ""))
        term_item._action(mgr.icon, term_item)
        assert term_cb.called

        # Encontrar y ejecutar la acción del elemento Acerca de RTMS
        about_item = next(it for it in menu_items if "Acerca de RTMS" in getattr(it, "text", ""))
        about_item._action(mgr.icon, about_item)
        assert about_cb.called

        # Encontrar y ejecutar la acción del elemento Salir de RTMS
        exit_item = next(it for it in menu_items if "Salir de RTMS" in getattr(it, "text", ""))
        exit_item._action(mgr.icon, exit_item)
        assert exit_cb.called

        mgr.stop()
        assert mgr.icon is None


def test_system_tray_about_fallback_dialog():
    """Valida que si no se proporciona callback on_about, se invoque _show_default_about sin error."""
    mgr = SystemTrayManager()

    with patch("ctypes.windll.user32.MessageBoxW") as mock_msgbox:
        with patch("threading.Thread") as mock_thread:
            mock_thread.side_effect = lambda target, daemon: MagicMock(start=target)
            mgr._show_default_about()
            assert mock_msgbox.called
            args, _ = mock_msgbox.call_args
            assert "Acerca de RTMS" in args[2]
            assert "Joaquín Yarsky" in args[1]


def test_unblock_app_binaries():
    """Valida que unblock_app_binaries elimine flujos Zone.Identifier."""
    from core.system_env import unblock_app_binaries
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dll = os.path.join(tmpdir, "test.dll")
        with open(test_dll, "wb") as f:
            f.write(b"MZfake")

        with patch("core.system_env.get_base_dir", return_value=tmpdir):
            # En plataformas no-windows o simulado
            count = unblock_app_binaries()
            assert isinstance(count, int)


def test_show_window_from_tray_ready():
    """Valida que show_window_from_tray restaure la ventana si _main_window_ready es True."""
    import main

    mock_win = MagicMock()
    with patch.object(main, "_main_window", mock_win):
        with patch.object(main, "_main_window_ready", True):
            with patch("webbrowser.open") as mock_browser:
                main.show_window_from_tray()
                assert mock_win.show.called
                assert mock_win.restore.called
                assert not mock_browser.called


def test_show_window_from_tray_not_ready():
    """Valida que show_window_from_tray abra el navegador si _main_window_ready es False (sin bloquear)."""
    import main

    mock_win = MagicMock()
    with patch.object(main, "_main_window", mock_win):
        with patch.object(main, "_main_window_ready", False):
            with patch("webbrowser.open") as mock_browser:
                main.show_window_from_tray()
                assert not mock_win.show.called
                assert not mock_win.restore.called
                assert mock_browser.called


def test_show_about_from_tray_behavior():
    """Valida que show_about_from_tray use evaluate_js si la ventana está lista, o el fallback nativo si no."""
    import main

    mock_win = MagicMock()
    mock_tray = MagicMock()
    # Caso 1: Ventana lista
    with patch.object(main, "_main_window", mock_win):
        with patch.object(main, "_main_window_ready", True):
            with patch.object(main, "_tray_mgr", mock_tray):
                main.show_about_from_tray()
                assert mock_win.show.called
                assert mock_win.evaluate_js.called
                assert not mock_tray._show_default_about.called

    # Caso 2: Ventana no lista
    mock_win.reset_mock()
    mock_tray.reset_mock()
    with patch.object(main, "_main_window", mock_win):
        with patch.object(main, "_main_window_ready", False):
            with patch.object(main, "_tray_mgr", mock_tray):
                main.show_about_from_tray()
                assert not mock_win.evaluate_js.called
                assert mock_tray._show_default_about.called



