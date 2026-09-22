# ==============================================================================
# RTMS — Real-Time Multicam System
# Control de instancia única de la aplicación en el sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Control de instancia única de la aplicación en Windows mediante Mutex del sistema."""

import ctypes
import logging
import sys
from ctypes import wintypes

logger = logging.getLogger("rtms.single_instance")

_GLOBAL_MUTEX = "Global\\RTMS_Multicam_v2_SingleInstance_Mutex"
_LOCAL_MUTEX = "Local\\RTMS_Multicam_v2_SingleInstance_Mutex"
_mutex_handle = None


def acquire_single_instance_lock(mutex_name: str | None = None) -> bool:
    """
    Intenta adquirir un Mutex en Windows para asegurar que solo una instancia
    de RTMS esté en ejecución a la vez. Intenta primero en el espacio Global
    y cae a Local si no cuenta con privilegios administrativos.
    Retorna True si esta es la única instancia, False si ya hay otra activa.
    """
    global _mutex_handle
    if sys.platform != "win32":
        return True

    ERROR_ALREADY_EXISTS = 183
    ERROR_ACCESS_DENIED = 5

    target_global = f"Global\\{mutex_name}" if mutex_name else _GLOBAL_MUTEX
    target_local = f"Local\\{mutex_name}" if mutex_name else _LOCAL_MUTEX

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        # 1. Intentar Mutex Global
        _mutex_handle = kernel32.CreateMutexW(None, False, target_global)
        last_error = ctypes.get_last_error()

        # Si da error de permisos en Global, caer al espacio Local
        if (not _mutex_handle or last_error == ERROR_ACCESS_DENIED) and last_error != ERROR_ALREADY_EXISTS:
            logger.debug("No se pudo crear mutex Global (permisos). Intentando mutex Local...")
            _mutex_handle = kernel32.CreateMutexW(None, False, target_local)
            last_error = ctypes.get_last_error()

        if not _mutex_handle or last_error == ERROR_ALREADY_EXISTS:
            logger.warning("Otra instancia de RTMS ya está en ejecución.")
            if _mutex_handle:
                try:
                    kernel32.CloseHandle(_mutex_handle)
                except Exception:
                    pass
                _mutex_handle = None
            return False

        logger.info("Mutex de instancia única adquirido exitosamente.")
        return True
    except Exception as e:
        logger.warning(f"Error comprobando instancia única: {e}")
        return True


def release_single_instance_lock():
    """Libera el handle del Mutex al cerrar la aplicación."""
    global _mutex_handle
    if _mutex_handle and sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(_mutex_handle)
            logger.info("Mutex de instancia única liberado.")
        except Exception as e:
            logger.warning(f"Error liberando mutex: {e}")
        finally:
            _mutex_handle = None
