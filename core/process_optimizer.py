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


def get_pcore_affinity_mask() -> Optional[int]:
    """
    Detecta la topología de la CPU en Windows NT y calcula la máscara de afinidad
    para los núcleos de alto rendimiento (P-Cores) en procesadores híbridos
    (Intel 12ª-15ª Gen, AMD con núcleos heterogéneos).

    En CPUs homogéneas o si no se detecta heterogeneidad, retorna la máscara de
    todos los núcleos lógicos disponibles en el sistema.
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class GROUP_AFFINITY(ctypes.Structure):
            _fields_ = [
                ("Mask", ctypes.c_size_t),
                ("Group", wintypes.WORD),
                ("Reserved", wintypes.WORD * 3),
            ]

        class PROCESSOR_RELATIONSHIP(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.BYTE),
                ("EfficiencyClass", wintypes.BYTE),
                ("Reserved", wintypes.BYTE * 20),
                ("GroupCount", wintypes.WORD),
                ("GroupMask", GROUP_AFFINITY * 1),
            ]

        class SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX(ctypes.Structure):
            _fields_ = [
                ("Relationship", wintypes.DWORD),
                ("Size", wintypes.DWORD),
                ("Processor", PROCESSOR_RELATIONSHIP),
            ]

        kernel32 = ctypes.windll.kernel32
        RelationProcessorCore = 0
        buf_len = wintypes.DWORD(0)

        kernel32.GetLogicalProcessorInformationEx(RelationProcessorCore, None, ctypes.byref(buf_len))
        if buf_len.value == 0:
            return None

        buf = (ctypes.c_byte * buf_len.value)()
        if not kernel32.GetLogicalProcessorInformationEx(RelationProcessorCore, buf, ctypes.byref(buf_len)):
            return None

        offset = 0
        cores = []
        while offset < buf_len.value:
            info = SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX.from_buffer(buf, offset)
            eff = info.Processor.EfficiencyClass
            mask = info.Processor.GroupMask[0].Mask
            cores.append((eff, mask))
            offset += info.Size

        if not cores:
            return None

        efficiencies = [c[0] for c in cores]
        max_eff = max(efficiencies)
        min_eff = min(efficiencies)

        if max_eff > min_eff:
            pcore_mask = 0
            for eff, mask in cores:
                if eff == max_eff:
                    pcore_mask |= mask
            logger.info(f"Topología de CPU híbrida detectada. Máscara P-Cores: {hex(pcore_mask)}")
            return pcore_mask

        all_mask = 0
        for _, mask in cores:
            all_mask |= mask
        return all_mask

    except Exception as e:
        logger.debug(f"Aviso al detectar afinidad de P-Cores: {e}")
        return None


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
                   If None, automatically attempts to detect and pin to P-Cores.

    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32" or not pid or not isinstance(pid, int):
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

            effective_mask = core_mask if core_mask is not None else get_pcore_affinity_mask()
            if effective_mask is not None:
                kernel32.SetProcessAffinityMask(h_process, ctypes.c_size_t(effective_mask))
                logger.info(
                    f"[PID {pid}] Elevated to priority 0x{priority_class:04X}, affinity mask: {hex(effective_mask)}"
                )
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
