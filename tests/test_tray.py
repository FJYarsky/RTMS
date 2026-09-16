# ==============================================================================
# RTMS — Real-Time Multicam System
# Tests de integración y menú contextual del System Tray de Windows
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

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

    with patch("threading.Thread") as mock_thread:
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

        # Encontrar y ejecutar la acción del elemento Acerca de RTMS
        about_item = next(it for it in menu_items if "Acerca de RTMS" in getattr(it, "text", ""))
        about_item._action(mgr.icon, about_item)
        assert about_cb.called

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
