# ==============================================================================
# RTMS v2.2.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

"""RTMS application entrypoint, desktop lifecycle, and CLI runner."""

import sys
import os
import time
import socket
import secrets
import threading
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
    _RES_DIR = getattr(sys, '_MEIPASS', _APP_DIR)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _RES_DIR = _APP_DIR

_BASE_DIR = _APP_DIR
sys.path.insert(0, _BASE_DIR)

from core.__version__ import __version__
from core.single_instance import acquire_single_instance_lock, release_single_instance_lock

import uvicorn
import webview
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from core.system_env import setup_firewall_rules, acquire_stay_awake, release_stay_awake
from core.ffmpeg_mgr import sync_streams_with_hardware, stream_manager
from core.tray_icon import SystemTrayManager
from api.routes import router as api_router, set_global_api_token

# Generación de token criptográfico de sesión local para proteger la API contra CSRF / drive-by
API_TOKEN = secrets.token_urlsafe(32)
set_global_api_token(API_TOKEN)

# Configuración de Logging con Rotación (5 MB x 3 copias para evitar crecimiento infinito)
_LOG_FILE = os.path.join(_BASE_DIR, "rtms.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rtms.main")

_main_window = None
_tray_mgr = None
_uvicorn_server = None
_uvicorn_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando RTMS API Backend v{__version__}...")
    setup_firewall_rules()
    acquire_stay_awake()

    # Sincronización inicial y autoarranque desatendido
    asyncio.create_task(sync_streams_with_hardware())

    # Tarea de fondo para detección continua de cámaras conectadas en caliente (hotplug)
    asyncio.create_task(stream_manager.start_periodic_hardware_sync())

    yield

    logger.info("Apagando backend RTMS. Deteniendo transmisiones de forma limpia...")
    try:
        await stream_manager.stop_all()
    except Exception as e:
        logger.error(f"Error deteniendo streams durante el shutdown: {e}")
    finally:
        release_stay_awake()

def create_app(token: str = API_TOKEN, port: Optional[int] = None) -> FastAPI:
    """Fábrica para instanciar la aplicación FastAPI, desacoplando dependencias."""
    set_global_api_token(token)
    application = FastAPI(title="RTMS API", version=__version__, lifespan=lifespan)
    application.state.api_token = token

    if port:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
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
            return tmpl.TemplateResponse(
                request=request,
                name="index.html",
                context={"api_token": token}
            )

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

    app_with_cors = create_app(token=API_TOKEN, port=port)
    config = uvicorn.Config(app_with_cors, host="127.0.0.1", port=port, log_level="warning", reload=False)
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.run()

_api_port = 8000

def show_window_from_tray():
    global _main_window, _api_port
    if _main_window:
        try:
            _main_window.show()
            _main_window.restore()
            return
        except Exception as e:
            logger.debug(f"Error restaurando ventana desde tray: {e}")
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{_api_port}")

def on_closed():
    """Cierre unificado y ordenado de la aplicación (sin os._exit abrupto)."""
    logger.info("Cierre de aplicación solicitado. Ejecutando protocolo ordenado...")
    global _tray_mgr, _uvicorn_server, _uvicorn_thread

    # 1. Detener System Tray
    if _tray_mgr:
        try:
            _tray_mgr.stop()
        except Exception as e:
            logger.debug(f"Error al detener system tray: {e}")

    # 2. Notificar a Uvicorn para cierre ordenado (su lifespan ejecutará stream_manager.stop_all)
    if _uvicorn_server:
        _uvicorn_server.should_exit = True

    if _uvicorn_thread and _uvicorn_thread.is_alive():
        _uvicorn_thread.join(timeout=3.0)

    # 3. Fallback: Si Uvicorn no estaba activo o no corrió lifespan, asegurar detención de streams
    try:
        if stream_manager.has_active_streams:
            asyncio.run(stream_manager.stop_all())
    except Exception as e:
        logger.debug(f"Aviso en verificación de detención de streams: {e}")

    # 4. Liberar bloqueo de instancia única
    release_single_instance_lock()

    # 5. Salida estándar de Python
    logger.info("RTMS cerrado exitosamente.")
    sys.exit(0)

if __name__ == "__main__":
    # 0. Verificación estricta de instancia única (Single Instance Lock)
    if not acquire_single_instance_lock():
        print("[INFO] RTMS ya se encuentra en ejecución en este equipo. Abortando instancia secundaria.")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "RTMS ya está abierto y ejecutándose en este equipo.", "RTMS — Instancia en Ejecución", 0x40)
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
    retries = 25
    while retries > 0 and not is_port_open("127.0.0.1", _api_port):
        time.sleep(0.2)
        retries -= 1

    if retries == 0:
        logger.error("No se pudo iniciar el servidor backend FastAPI. Abortando.")
        release_single_instance_lock()
        sys.exit(1)

    logger.info(f"FastAPI iniciado con éxito en puerto {_api_port}. Configurando interfaz nativa...")

    # 3. Inicializar icono en la bandeja del sistema (System Tray)
    _tray_mgr = SystemTrayManager(
        on_show_window=show_window_from_tray,
        on_exit_app=on_closed
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

    # 5. Crear ventana nativa con pywebview
    try:
        _main_window = webview.create_window(
            title=f"RTMS v{__version__} — Real-Time Multicam System",
            url=f"http://127.0.0.1:{_api_port}",
            width=1280,
            height=820,
            min_size=(980, 620),
            background_color="#0b0f19"
        )
        _main_window.events.closing += on_window_closing
        webview.start()
    except Exception as e:
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
