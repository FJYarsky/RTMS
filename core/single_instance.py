# ==============================================================================
# RTMS — Real-Time Multicam System v2.0.2
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import sys
import ctypes
import logging

logger = logging.getLogger("rtms.single_instance")

_MUTEX_NAME = "Global\\RTMS_Multicam_v2_SingleInstance_Mutex"
_mutex_handle = None

def acquire_single_instance_lock() -> bool:
    """
    Intenta adquirir un Mutex global en Windows para asegurar que solo
    una instancia de RTMS esté en ejecución a la vez.
    Retorna True si esta es la única instancia, False si ya hay otra activa.
    """
    global _mutex_handle
    if sys.platform != "win32":
        return True

    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32

    # Intentamos crear el mutex
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    last_error = kernel32.GetLastError()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("Otra instancia de RTMS ya está en ejecución.")
        return False

    logger.info("Mutex de instancia única adquirido exitosamente.")
    return True

def release_single_instance_lock():
    """Libera el handle del Mutex al cerrar la aplicación."""
    global _mutex_handle
    if _mutex_handle and sys.platform == "win32":
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            logger.info("Mutex de instancia única liberado.")
        except Exception as e:
            logger.warning(f"Error liberando mutex: {e}")
