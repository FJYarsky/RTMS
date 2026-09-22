# ==============================================================================
# RTMS — Real-Time Multicam System
# Punto de entrada principal y ciclo de vida de la aplicación.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Punto de entrada principal y ciclo de vida de la aplicación."""

import asyncio
import io
import logging
import os
import secrets
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from typing import Optional


class _NullWriter(io.StringIO):
    """Fallback stream writer for GUI / noconsole environments where stdout/stderr is None."""

    def write(self, s: str) -> int:
        return len(s) if s else 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
    _RES_DIR = getattr(sys, "_MEIPASS", _APP_DIR)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _RES_DIR = _APP_DIR

_BASE_DIR = _APP_DIR
sys.path.insert(0, _BASE_DIR)

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.deps import set_global_api_token
from api.routes import router as api_router
from core.__version__ import __version__
from core.config_mgr import get_base_dir
from core.hardware_sync import sync_streams_with_hardware
from core.preview_mgr import preview_manager
from core.process_cleanup import terminate_all_processes
from core.sanitizer import SecretFilter
from core.single_instance import acquire_single_instance_lock, release_single_instance_lock
from core.stream_manager import stream_manager
from core.system_env import (
    acquire_stay_awake,
    get_platform_details,
    release_stay_awake,
    setup_firewall_rules,
    unblock_app_binaries,
)
from core.telemetry import telemetry_service
from core.tray_icon import SystemTrayManager

# Generación de token criptográfico de sesión local para proteger la API contra CSRF / drive-by
API_TOKEN = secrets.token_urlsafe(32)
set_global_api_token(API_TOKEN)

# Configuración de Logging con Rotación y Filtro de Secretos
_STORAGE_DIR = get_base_dir()
_LOG_FILE = os.path.join(_STORAGE_DIR, "rtms.log")
secret_filter = SecretFilter()
file_handler = RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.addFilter(secret_filter)

handlers = [file_handler]
if sys.stderr is not None and not isinstance(sys.stderr, _NullWriter):
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.addFilter(secret_filter)
    handlers.append(stream_handler)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=handlers)
logger = logging.getLogger("rtms.main")

_main_window = None
_main_window_ready = False
_tray_mgr = None
_uvicorn_server = None
_uvicorn_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando RTMS API Backend v{__version__}...")
    app.state.loop = asyncio.get_running_loop()
    setup_firewall_rules()
    acquire_stay_awake()

    # Sincronización inicial y autoarranque desatendido
    asyncio.create_task(sync_streams_with_hardware())

    # Tarea de fondo para detección continua de cámaras conectadas en caliente (hotplug)
    asyncio.create_task(stream_manager.start_periodic_hardware_sync())

    yield

    logger.info("Apagando backend RTMS. Deteniendo transmisiones y previsualizaciones limpiamente...")
    try:
        await stream_manager.stop_all()
    except Exception as e:
        logger.error(f"Error deteniendo streams durante el shutdown: {e}")
    try:
        await preview_manager.stop_all()
    except Exception as e:
        logger.error(f"Error deteniendo previews durante el shutdown: {e}")
    try:
        telemetry_service.shutdown()
    except Exception as e:
        logger.error(f"Error en shutdown de telemetría: {e}")
    finally:
        release_stay_awake()


def create_app(token: str = API_TOKEN, port: Optional[int] = None) -> FastAPI:
    """Fábrica para instanciar la aplicación FastAPI, desacoplando dependencias."""
    set_global_api_token(token)
    application = FastAPI(title="RTMS API", version=__version__, lifespan=lifespan)
    application.state.api_token = token

    # Middleware de cabeceras de seguridad HTTP
    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    if port:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )

    application.include_router(api_router)

    _static_dir = os.path.join(_RES_DIR, "gui", "static")
    if not os.path.exists(_static_dir):
        _static_dir = os.path.join(_APP_DIR, "gui", "static")

    _templates_dir = os.path.join(_RES_DIR, "gui", "templates")
    if not os.path.exists(_templates_dir):
        _templates_dir = os.path.join(_APP_DIR, "gui", "templates")

    if os.path.exists(_static_dir):
        application.mount("/static", StaticFiles(directory=_static_dir), name="static")

    if os.path.exists(_templates_dir):
        tmpl = Jinja2Templates(directory=_templates_dir)

        @application.get("/")
        async def root(request: Request):
            platform_info = get_platform_details()
            response = tmpl.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "version": __version__,
                    "platform_info": platform_info,
                },
            )
            if token:
                response.set_cookie(key="rtms_session", value=token, httponly=True, samesite="strict")
            return response

    return application


app = create_app()


def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            return True
    except OSError:
        return False


def get_free_port(start_port=8000, end_port=8099) -> int:
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No hay puertos libres disponibles para iniciar la API.")


def run_fastapi(port: int):
    global _uvicorn_server
    logger.info(f"Lanzando servidor de API local en puerto {port}...")
    try:
        app_with_cors = create_app(token=API_TOKEN, port=port)
        config = uvicorn.Config(
            app_with_cors, host="127.0.0.1", port=port, log_level="warning", log_config=None, reload=False
        )
        _uvicorn_server = uvicorn.Server(config)
        _uvicorn_server.run()
    except Exception as e:
        logger.exception(f"Fallo crítico en servidor Uvicorn: {e}")


_api_port = 8000


def show_window_from_tray():
    global _main_window, _main_window_ready, _api_port
    if _main_window is not None and _main_window_ready:
        try:
            _main_window.show()
            _main_window.restore()
            return
        except Exception as e:
            logger.warning(f"No se pudo restaurar la ventana nativa: {e}")

    # Si no hay ventana nativa lista (entorno sin GUI pywebview o fallback), abrir navegador
    try:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{_api_port}")
    except Exception as e:
        logger.error(f"Error abriendo navegador web: {e}")


def show_about_from_tray():
    """Restaura la ventana principal y abre el modal Acerca de, o muestra diálogo nativo si no hay GUI."""
    global _main_window, _main_window_ready, _tray_mgr
    opened_in_window = False
    if _main_window is not None and _main_window_ready:
        try:
            _main_window.show()
            _main_window.restore()
            _main_window.evaluate_js("if (typeof openAboutModal === 'function') openAboutModal();")
            opened_in_window = True
        except Exception as e:
            logger.debug(f"Aviso al mostrar modal Acerca de en ventana nativa: {e}")

    if not opened_in_window and _tray_mgr is not None:
        _tray_mgr._show_default_about()


def on_closed():
    """Cierre unificado y ordenado de la aplicación."""
    logger.info("Cierre de aplicación solicitado. Ejecutando protocolo ordenado...")
    global _tray_mgr, _uvicorn_server, _uvicorn_thread

    # 1. Detener System Tray
    if _tray_mgr:
        try:
            _tray_mgr.stop()
        except Exception as e:
            logger.debug(f"Error al detener system tray: {e}")

    # 2. Notificar a Uvicorn para cierre ordenado
    if _uvicorn_server:
        _uvicorn_server.should_exit = True

    if _uvicorn_thread and _uvicorn_thread.is_alive():
        _uvicorn_thread.join(timeout=2.0)

    # 3. Limpieza profunda y terminación de subprocesos
    terminate_all_processes(force=False)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()

    # Desbloquear binarios y bibliotecas en Windows (Mark-of-the-Web / Zone.Identifier)
    unblock_app_binaries()

    # 0. Verificación estricta de instancia única (Single Instance Lock)
    if not acquire_single_instance_lock():
        print("[INFO] RTMS ya se encuentra en ejecución en este equipo. Abortando instancia secundaria.")
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, "RTMS ya está abierto y ejecutándose en este equipo.", "RTMS — Instancia en Ejecución", 0x40
            )
        except Exception:
            pass
        sys.exit(0)

    try:
        _api_port = get_free_port()
    except Exception as e:
        logger.error(str(e))
        release_single_instance_lock()
        sys.exit(1)

    # 1. Iniciar FastAPI en segundo plano
    _uvicorn_thread = threading.Thread(target=run_fastapi, args=(_api_port,), daemon=True)
    _uvicorn_thread.start()

    # 2. Esperar a que FastAPI esté listo
    retries = 30
    while retries > 0 and not is_port_open("127.0.0.1", _api_port):
        if not _uvicorn_thread.is_alive():
            logger.error("El hilo de FastAPI finalizó inesperadamente durante el arranque. Abortando.")
            release_single_instance_lock()
            sys.exit(1)
        time.sleep(0.2)
        retries -= 1

    if retries == 0:
        logger.error("No se pudo iniciar el servidor backend FastAPI. Tiempo de espera agotado. Abortando.")
        release_single_instance_lock()
        sys.exit(1)

    logger.info(f"FastAPI iniciado con éxito en puerto {_api_port}. Configurando interfaz nativa...")

    def _handle_tray_stop_streams():
        logger.info("Detención de transmisiones solicitada desde la bandeja del sistema.")
        loop = getattr(app.state, "loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(stream_manager.stop_all(), loop)
        else:
            try:
                asyncio.run(stream_manager.stop_all())
            except Exception as e:
                logger.debug(f"Aviso deteniendo streams desde tray: {e}")

    def _handle_tray_terminate_all():
        logger.info("Finalización total de procesos solicitada desde la bandeja del sistema.")
        if _tray_mgr:
            try:
                _tray_mgr.stop()
            except Exception:
                pass
        terminate_all_processes(force=True)

    # 3. Inicializar icono en la bandeja del sistema (System Tray)
    _tray_mgr = SystemTrayManager(
        on_show_window=show_window_from_tray,
        on_stop_streams=_handle_tray_stop_streams,
        on_terminate_all=_handle_tray_terminate_all,
        on_exit_app=on_closed,
        on_about=show_about_from_tray,
    )
    _tray_mgr.start()

    # 4. Manejador para minimizar al System Tray al cerrar la ventana ('X')
    def on_window_closing():
        if _main_window:
            try:
                _main_window.hide()
                return False  # Cancela el cierre definitivo para continuar en segundo plano
            except Exception:
                pass
        return True

    # 5. Crear ventana nativa con pywebview (importación perezosa/segura P4)
    def on_window_ready():
        global _main_window_ready
        _main_window_ready = True
        logger.info("Ventana nativa WebView2 inicializada y lista.")

    try:
        import webview

        _main_window = webview.create_window(
            title=f"RTMS v{__version__} — Real-Time Multicam System",
            url=f"http://127.0.0.1:{_api_port}",
            width=1280,
            height=820,
            min_size=(980, 620),
            background_color="#0b0f19",
        )
        _main_window.events.closing += on_window_closing
        webview.start(func=on_window_ready, gui="edgechromium")
    except Exception as e:
        _main_window = None
        _main_window_ready = False
        logger.warning(f"No se pudo iniciar pywebview nativo: {e}")
        logger.info(f"Iniciando RTMS en segundo plano con acceso vía navegador en: http://127.0.0.1:{_api_port}")
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{_api_port}")

    # Si webview finaliza o corre en modo tray/browser, mantener el hilo principal activo
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        on_closed()
