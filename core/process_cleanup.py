# ==============================================================================
# RTMS — Real-Time Multicam System
# Terminación y limpieza de procesos del sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import os
import logging
import asyncio
import psutil

logger = logging.getLogger("rtms.cleanup")

def terminate_all_processes(force: bool = True):
    """
    Finaliza totalmente la ejecución de RTMS y todos sus subprocesos (FFmpeg, FFplay).
    Detiene flujos, apaga telemetría, mata procesos hijos y libera el mutex de instancia única.
    """
    logger.warning("Terminación total de todos los procesos solicitada por el usuario.")

    # 1. Detener streams y previews en memoria
    try:
        from core.ffmpeg_mgr import stream_manager
        from core.preview_mgr import preview_manager

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                asyncio.gather(stream_manager.stop_all(), preview_manager.stop_all(), return_exceptions=True),
                loop
            )
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
        else:
            loop.run_until_complete(
                asyncio.gather(stream_manager.stop_all(), preview_manager.stop_all(), return_exceptions=True)
            )
    except Exception as e:
        logger.debug(f"Aviso deteniendo managers de streaming: {e}")

    # 2. Apagar telemetría y suspender stay_awake
    try:
        from core.telemetry import telemetry_service
        telemetry_service.shutdown()
    except Exception:
        pass

    try:
        from core.system_env import release_stay_awake
        release_stay_awake()
    except Exception:
        pass

    # 3. Terminar árbol de procesos secundarios (FFmpeg, FFplay)
    try:
        current_proc = psutil.Process(os.getpid())
        children = current_proc.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        # Esperar hasta 1.5 segundos
        _, still_alive = psutil.wait_procs(children, timeout=1.5)
        for child in still_alive:
            try:
                child.kill()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Aviso al limpiar procesos secundarios vía psutil: {e}")

    # 4. Matar cualquier proceso huérfano ffmpeg/ffplay remanente si force=True
    if force:
        try:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = (p.info.get('name') or '').lower()
                    if name in ('ffmpeg.exe', 'ffplay.exe'):
                        p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

    # 5. Liberar Mutex de instancia única
    try:
        from core.single_instance import release_single_instance_lock
        release_single_instance_lock()
    except Exception:
        pass

    logger.info("Todos los procesos de RTMS han sido terminados.")
    os._exit(0)
