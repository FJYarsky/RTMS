# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.3
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

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

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from core.single_instance import acquire_single_instance_lock, release_single_instance_lock

# 0. Verificación estricta de instancia única (Single Instance Lock)
if not acquire_single_instance_lock():
    print("[INFO] RTMS ya se encuentra en ejecución en este equipo. Abortando instancia secundaria.")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "RTMS ya está abierto y ejecutándose en este equipo.", "RTMS — Instancia en Ejecución", 0x40)
    except Exception:
        pass
    sys.exit(0)

import uvicorn
import webview
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from core.system_env import setup_firewall_rules
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando RTMS API Backend v2.0.3...")
    setup_firewall_rules()
    
    # Sincronización inicial y autoarranque desatendido
    asyncio.create_task(sync_streams_with_hardware())
    
    # Tarea de fondo para detección continua de cámaras conectadas en caliente (hotplug)
    asyncio.create_task(stream_manager.start_periodic_hardware_sync())
    
    yield
    
    logger.info("Apagando backend RTMS. Deteniendo transmisiones de forma limpia...")
    try:
        await stream_manager.emergency_stop_all()
    except Exception as e:
        logger.error(f"Error deteniendo streams durante el shutdown: {e}")

app = FastAPI(title="RTMS API", version="2.0.3", lifespan=lifespan)

# Endpoint público de salud para supervisores de sistema (NSSM, scripts externos)
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "version": "2.0.3"}

# Montar endpoints de la API
app.include_router(api_router)

_STATIC_DIR = os.path.join(_BASE_DIR, "gui", "static")
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "gui", "templates")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"api_token": API_TOKEN}
    )

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
    
    # Restringir CORS estrictamente al origen dinámico local para prevenir localhost CSRF
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", reload=False)
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.run()

def show_window_from_tray():
    global _main_window
    if _main_window:
        try:
            _main_window.show()
            _main_window.restore()
        except Exception as e:
            logger.debug(f"Error restaurando ventana desde tray: {e}")

def on_closed():
    """Cierre ordenado de la aplicación."""
    logger.info("Ventana cerrada por el usuario. Finalizando aplicación...")
    global _tray_mgr, _uvicorn_server
    if _tray_mgr:
        _tray_mgr.stop()
        
    try:
        for dp, proc in stream_manager._procs.items():
            if proc.process and proc.process.returncode is None:
                try:
                    proc.process.kill()
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error durante limpieza de procesos FFmpeg: {e}")
        
    release_single_instance_lock()
    
    if _uvicorn_server:
        _uvicorn_server.should_exit = True
        
    os._exit(0)

if __name__ == "__main__":
    try:
        api_port = get_free_port()
    except Exception as e:
        logger.error(str(e))
        release_single_instance_lock()
        sys.exit(1)

    # 1. Iniciar FastAPI en segundo plano
    t = threading.Thread(target=run_fastapi, args=(api_port,), daemon=True)
    t.start()

    # 2. Esperar a que FastAPI esté listo
    retries = 25
    while retries > 0 and not is_port_open("127.0.0.1", api_port):
        time.sleep(0.2)
        retries -= 1

    if retries == 0:
        logger.error("No se pudo iniciar el servidor backend FastAPI. Abortando.")
        release_single_instance_lock()
        sys.exit(1)

    logger.info("FastAPI iniciado con éxito. Configurando interfaz nativa...")

    # 3. Inicializar icono en la bandeja del sistema (System Tray)
    _tray_mgr = SystemTrayManager(
        on_show_window=show_window_from_tray,
        on_exit_app=on_closed
    )
    _tray_mgr.start()

    # 4. Crear ventana nativa con pywebview
    _main_window = webview.create_window(
        title="RTMS v2.0.3 — Real-Time Multicam System",
        url=f"http://127.0.0.1:{api_port}",
        width=1280,
        height=820,
        min_size=(980, 620),
        background_color="#0b0f19"
    )

    _main_window.events.closed += on_closed
    webview.start()
