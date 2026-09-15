# ==============================================================================
# RTMS v2.1.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import os
import sys
import logging
import threading
from PIL import Image, ImageDraw

from core.__version__ import __version__

logger = logging.getLogger("rtms.tray")

class SystemTrayManager:
    def __init__(self, on_show_window=None, on_exit_app=None):
        self.on_show_window = on_show_window
        self.on_exit_app = on_exit_app
        self.icon = None
        self._thread = None

    def _create_fallback_image(self):
        # Crear un icono 64x64 con un círculo Teal
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Círculo Teal
        draw.ellipse([8, 8, 56, 56], fill=(20, 184, 166, 255), outline=(13, 148, 136, 255), width=2)
        # Letra 'R'
        draw.rectangle([26, 20, 38, 44], fill=(11, 15, 25, 255))
        return img

    def _get_icon_image(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        ico_path = os.path.join(base_dir, "icon.ico")
        if os.path.exists(ico_path):
            try:
                return Image.open(ico_path)
            except Exception as e:
                logger.warning(f"No se pudo cargar icon.ico: {e}")
        return self._create_fallback_image()

    def start(self):
        try:
            import pystray
        except ImportError:
            logger.warning("pystray no está disponible. Modo bandeja del sistema desactivado.")
            return

        image = self._get_icon_image()

        def _show(icon, item):
            if self.on_show_window:
                self.on_show_window()

        def _exit(icon, item):
            icon.stop()
            if self.on_exit_app:
                self.on_exit_app()

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar RTMS", _show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir de RTMS", _exit)
        )

        self.icon = pystray.Icon("RTMS", image, f"RTMS v{__version__}", menu)

        # Iniciar en hilo independiente para no bloquear
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        logger.info("Icono de bandeja del sistema (System Tray) iniciado.")

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
