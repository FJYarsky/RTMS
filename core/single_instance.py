# ==============================================================================
# RTMS v2.2.2 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import sys
import ctypes
from ctypes import wintypes
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
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    # Intentamos crear el mutex
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    last_error = ctypes.get_last_error()

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
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            logger.info("Mutex de instancia única liberado.")
        except Exception as e:
            logger.warning(f"Error liberando mutex: {e}")

