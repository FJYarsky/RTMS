# ==============================================================================
# RTMS — Real-Time Multicam System
# Blindaje de procesos secundarios a nivel de Kernel (Win32 Job Objects).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Módulo de gestión de Windows Job Objects.
Asegura que todos los subprocesos secundarios (FFmpeg, MediaMTX, FFplay)
sean liquidados de forma determinista por el Kernel de Windows si el proceso
principal de RTMS finaliza, se aborta o se termina abruptamente.
"""

import atexit
import ctypes
import logging
import subprocess
import sys
from ctypes import wintypes
from typing import Any, Optional, Union

logger = logging.getLogger("rtms.job_object")

# Constantes Win32
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_ALL_ACCESS = 0x1F0FFF

# Definición de estructuras ctypes para Job Objects en Windows
if sys.platform == "win32":

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryLimit", ctypes.c_size_t),
            ("PeakJobMemoryLimit", ctypes.c_size_t),
        ]
else:
    IO_COUNTERS = Any  # type: ignore[misc, assignment]
    JOBOBJECT_BASIC_LIMIT_INFORMATION = Any  # type: ignore[misc, assignment]
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION = Any  # type: ignore[misc, assignment]


class JobObjectManager:
    """
    Administrador singleton del Win32 Job Object principal de RTMS.
    Aplica el flag JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE para que el sistema operativo
    garantice que ningún subproceso quede huérfano.
    """

    def __init__(self) -> None:
        self.job_handle: Optional[wintypes.HANDLE] = None
        self._initialized = False
        self._is_supported = sys.platform == "win32"
        if self._is_supported:
            self._init_job_object()

    def _init_job_object(self) -> None:
        if not self._is_supported:
            return

        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Crear Job Object anónimo
            self.job_handle = kernel32.CreateJobObjectW(None, None)
            if not self.job_handle:
                err = ctypes.GetLastError()
                logger.warning(f"No se pudo crear Job Object Win32 (Error Win32 {err}). Continuando sin blindaje.")
                return

            # Configurar flags para que Windows mate automáticamente los subprocesos al cerrar el Job
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

            res = kernel32.SetInformationJobObject(
                self.job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not res:
                err = ctypes.GetLastError()
                logger.warning(f"Fallo al configurar JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (Error {err}).")
                kernel32.CloseHandle(self.job_handle)
                self.job_handle = None
                return

            self._initialized = True
            logger.info("Win32 Job Object inicializado con JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.")
        except Exception as e:
            logger.warning(f"Excepción inicializando Win32 Job Object: {e}")
            self.job_handle = None

    def is_active(self) -> bool:
        """Indica si el Job Object está activo y operativo."""
        return self._initialized and self.job_handle is not None

    def assign_process(self, proc: Union[subprocess.Popen, int]) -> bool:
        """
        Asocia un subproceso al Job Object.
        Acepta una instancia de subprocess.Popen o un PID entero.
        Maneja defensivamente entornos anidados donde AssignProcessToJobObject
        pueda retornar ERROR_ACCESS_DENIED (5).
        """
        if not self.is_active():
            return False

        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            if isinstance(proc, subprocess.Popen):
                # Si es un Popen en Windows, _handle es el handle nativo del proceso
                h_process = getattr(proc, "_handle", None)
                if h_process is None and proc.pid:
                    h_process = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc.pid)
            elif isinstance(proc, int):
                h_process = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc)
            else:
                logger.warning(f"Tipo de proceso no soportado para Job Object: {type(proc)}")
                return False

            if not h_process:
                err = ctypes.GetLastError()
                logger.debug(f"OpenProcess falló para asignación a Job Object (Win32 {err}).")
                return False

            success = kernel32.AssignProcessToJobObject(self.job_handle, int(h_process))
            if not success:
                err = ctypes.GetLastError()
                # Error 5 = Access Denied (típico cuando el proceso ya pertenece a un Job que no permite anidación)
                # Error 6 = Invalid Handle
                if err in (5, 6):
                    logger.debug(
                        f"AssignProcessToJobObject omitido (Win32 {err} - proceso en contenedor o terminal anidada)."
                    )
                else:
                    logger.warning(f"Error asignando proceso {getattr(proc, 'pid', proc)} al Job Object (Win32 {err}).")
                return False

            logger.debug(f"Proceso PID {getattr(proc, 'pid', proc)} asignado exitosamente al Job Object de RTMS.")
            return True
        except Exception as e:
            logger.debug(f"Excepción al asociar proceso a Job Object: {e}")
            return False

    def close(self) -> None:
        """Cierra el handle del Job Object de forma segura."""
        if self.job_handle and self._is_supported:
            try:
                kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                kernel32.CloseHandle(self.job_handle)
            except Exception as e:
                logger.debug(f"Error cerrando handle de Job Object: {e}")
            finally:
                self.job_handle = None
                self._initialized = False


# Instancia singleton a nivel de módulo retenida para evitar GC prematuro
job_object_mgr = JobObjectManager()

# Registro de cierre ordenado en atexit
atexit.register(job_object_mgr.close)
