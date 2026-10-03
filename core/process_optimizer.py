# ==============================================================================
# RTMS — Real-Time Multicam System
# Optimizador de procesos y prioridades del planificador de Windows NT.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
RTMS Process Optimizer — Windows NT Process Priority & CPU Affinity Helper.

Elevates FFmpeg and MediaMTX child processes to HIGH_PRIORITY_CLASS to prevent
scheduler priority inversion under multi-camera CPU load.

Created for v2.9.0 — Low Latency Optimization Release.
"""

import logging
import sys
from typing import Dict, Optional

logger = logging.getLogger("rtms.optimizer")

# Windows NT Process Priority Classes
REALTIME_PRIORITY_CLASS = 0x00000100
HIGH_PRIORITY_CLASS = 0x00000080
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
NORMAL_PRIORITY_CLASS = 0x00000020

# Required access rights
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_INFORMATION = 0x0400


def elevate_process_priority(
    pid: int,
    priority_class: int = HIGH_PRIORITY_CLASS,
    core_mask: Optional[int] = None,
) -> bool:
    """
    Elevate a Windows process to HIGH_PRIORITY_CLASS and optionally
    pin it to specific CPU cores via affinity mask.

    Args:
        pid: Process ID to elevate.
        priority_class: Windows priority class constant.
        core_mask: Optional CPU core affinity bitmask (e.g. 0x0F for cores 0-3).

    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32" or not pid:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32

        h_process = kernel32.OpenProcess(
            PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION,
            False,
            pid,
        )
        if not h_process:
            logger.warning(f"[PID {pid}] Failed to open process handle (error {ctypes.get_last_error()})")
            return False

        try:
            result = kernel32.SetPriorityClass(h_process, priority_class)
            if not result:
                logger.warning(f"[PID {pid}] SetPriorityClass failed (error {ctypes.get_last_error()})")
                return False

            if core_mask is not None:
                kernel32.SetProcessAffinityMask(h_process, ctypes.c_size_t(core_mask))
                logger.info(f"[PID {pid}] Elevated to priority 0x{priority_class:04X}, affinity mask: {hex(core_mask)}")
            else:
                logger.info(f"[PID {pid}] Elevated to priority 0x{priority_class:04X}")

            return True
        finally:
            kernel32.CloseHandle(h_process)

    except Exception as e:
        logger.debug(f"[PID {pid}] Priority elevation failed: {e}")
        return False


def elevate_streaming_processes(
    ffmpeg_pid: Optional[int] = None,
    mediamtx_pid: Optional[int] = None,
    core_mask: Optional[int] = None,
) -> Dict[str, bool]:
    """
    Convenience wrapper to elevate both FFmpeg and MediaMTX processes.

    Returns:
        Dict with 'ffmpeg' and 'mediamtx' keys indicating success.
    """
    results: Dict[str, bool] = {}
    if ffmpeg_pid:
        results["ffmpeg"] = elevate_process_priority(ffmpeg_pid, HIGH_PRIORITY_CLASS, core_mask)
    if mediamtx_pid:
        results["mediamtx"] = elevate_process_priority(mediamtx_pid, HIGH_PRIORITY_CLASS, core_mask)
    return results
