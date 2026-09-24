# ==============================================================================
# RTMS — Real-Time Multicam System
# Integración y control del icono en la bandeja del sistema de Windows.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Integración y menú contextual de la aplicación en la bandeja del sistema (System Tray)."""

import logging
import os
import sys
import threading

from PIL import Image, ImageDraw

from core.__version__ import __version__

logger = logging.getLogger("rtms.tray")


class SystemTrayManager:
    def __init__(
        self, on_show_window=None, on_stop_streams=None, on_terminate_all=None, on_exit_app=None, on_about=None
    ):
        self.on_show_window = on_show_window
        self.on_stop_streams = on_stop_streams
        self.on_terminate_all = on_terminate_all
        self.on_exit_app = on_exit_app
        self.on_about = on_about
        self.icon = None
        self._thread = None

    def _create_fallback_image(self):
        """Genera un icono de respaldo de 64x64 HD con el diseño de obturador dinámico oficial de RTMS."""
        import math

        img = Image.new("RGBA", (128, 128), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Base con esquinas redondeadas en pizarra oscura (#111827) y contorno teal suave
        draw.rounded_rectangle([6, 6, 122, 122], radius=28, fill=(17, 24, 39, 255), outline=(20, 184, 166, 70), width=2)

        cx, cy = 64.0, 64.0
        R = 48.0
        r = 16.0
        alpha = math.acos(r / R)
        seam_width = 2
        seam_color = (17, 24, 39, 255)

        blade_colors = [
            (56, 189, 248, 255),  # Sky Cyan
            (45, 202, 242, 255),
            (34, 211, 238, 255),  # Bright Cyan
            (20, 184, 166, 255),  # Primary Teal
            (16, 166, 150, 255),
            (13, 148, 136, 255),  # Deep Teal
        ]

        for k in range(6):
            theta = math.radians(k * 60)
            phi = theta + math.pi / 6
            ang_out1 = phi - alpha
            ang_out2 = ang_out1 + math.radians(60)
            hex_ang = phi + math.radians(30)
            r_hex = r / math.cos(math.radians(30))
            p_hex = (cx + r_hex * math.cos(hex_ang), cy + r_hex * math.sin(hex_ang))

            poly_points = [p_hex]
            steps = 16
            for s in range(steps + 1):
                cur_ang = ang_out1 + (ang_out2 - ang_out1) * (s / steps)
                poly_points.append((cx + R * math.cos(cur_ang), cy + R * math.sin(cur_ang)))

            draw.polygon(poly_points, fill=blade_colors[k])
            draw.line([poly_points[0], poly_points[1]], fill=seam_color, width=seam_width)
            draw.line([poly_points[0], poly_points[-1]], fill=seam_color, width=seam_width)

        return img.resize((64, 64), Image.Resampling.LANCZOS)

    def _get_icon_image(self):
        """Busca el icono oficial icon.ico en múltiples ubicaciones antes de recurrir al fallback generado."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = []

        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.extend(
                [
                    os.path.join(exe_dir, "icon.ico"),
                    os.path.join(exe_dir, "_internal", "icon.ico"),
                    os.path.join(getattr(sys, "_MEIPASS", exe_dir), "icon.ico"),
                ]
            )

        candidates.extend(
            [os.path.join(base_dir, "icon.ico"), os.path.join(base_dir, "_internal", "icon.ico"), "icon.ico"]
        )

        for ico_path in candidates:
            if os.path.exists(ico_path):
                try:
                    img = Image.open(ico_path)
                    img.load()
                    return img
                except Exception as e:
                    logger.debug(f"Aviso al cargar {ico_path}: {e}")

        return self._create_fallback_image()

    def start(self):
        try:
            import pystray
        except ImportError:
            logger.warning("pystray no está disponible. Modo bandeja del sistema desactivado.")
            return

        image = self._get_icon_image()

        def _dispatch_async(fn, *args, **kwargs):
            """Despacha la acción en un hilo separado de forma inmediata para mantener la bomba de mensajes Win32 100% responsiva."""
            if fn:
                threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()

        def _show(icon, item):
            _dispatch_async(self.on_show_window)

        def _stop_all(icon, item):
            def _do_stop():
                if self.on_stop_streams:
                    self.on_stop_streams()
                else:
                    try:
                        import asyncio

                        from core.stream_manager import stream_manager

                        asyncio.run(stream_manager.stop_all())
                    except Exception as e:
                        logger.debug(f"Aviso deteniendo streams desde tray: {e}")

            _dispatch_async(_do_stop)

        def _terminate(icon, item):
            def _do_terminate():
                if self.on_terminate_all:
                    self.on_terminate_all()
                else:
                    try:
                        from core.process_cleanup import terminate_all_processes

                        terminate_all_processes(force=True)
                    except Exception:
                        sys.exit(0)

            _dispatch_async(_do_terminate)

        def _about(icon, item):
            def _do_about():
                if self.on_about:
                    self.on_about()
                else:
                    self._show_default_about()

            _dispatch_async(_do_about)

        def _exit(icon, item):
            def _do_exit():
                try:
                    icon.stop()
                except Exception:
                    pass
                if self.on_exit_app:
                    self.on_exit_app()

            _dispatch_async(_do_exit)

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar RTMS", _show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Detener todas las transmisiones", _stop_all),
            pystray.MenuItem("Finalizar todos los procesos", _terminate),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Acerca de RTMS", _about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir de RTMS", _exit),
        )

        self.icon = pystray.Icon("RTMS", image, f"RTMS v{__version__} — Real-Time Multicam System", menu)

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        logger.info("Icono de bandeja del sistema (System Tray) iniciado con opciones completas.")

    def _show_default_about(self):
        """Muestra un cuadro de diálogo nativo de Windows con la información oficial de RTMS."""
        try:
            import ctypes

            title = "Acerca de RTMS"
            msg = (
                f"RTMS — Real-Time Multicam System v{__version__}\n\n"
                "Servidor de video multicámara de baja latencia para Windows utilizando SRT y DirectShow.\n\n"
                "Desarrollador: Joaquín Yarsky (joaquinyarsky@gmail.com)\n"
                "Repositorio: https://github.com/FJYarsky/RTMS\n"
                "Licencia: MIT"
            )
            # MB_OK (0x0) | MB_ICONINFORMATION (0x40) | MB_SETFOREGROUND (0x10000) | MB_TOPMOST (0x40000)
            flags = 0x40 | 0x10000 | 0x40000
            threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(0, msg, title, flags), daemon=True).start()
        except Exception as e:
            logger.warning(f"No se pudo mostrar el diálogo Acerca de: {e}")

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
