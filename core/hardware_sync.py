# ==============================================================================
# RTMS — Real-Time Multicam System
# Sincronización de hardware DirectShow y consolidación de estados.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Sincronización del inventario de dispositivos DirectShow con el gestor de streams."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rtms.hardware_sync")


async def sync_streams_with_hardware(mgr: Optional[Any] = None) -> None:
    """Sincroniza el inventario de cámaras con el hardware DirectShow detectado."""
    if mgr is None:
        from core.stream_manager import stream_manager

        mgr = stream_manager
    await mgr.sync_streams_with_hardware()


def get_all_stream_statuses(mgr: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Retorna la lista consolidada de estados de todos los streams y dispositivos."""
    if mgr is None:
        from core.stream_manager import stream_manager

        mgr = stream_manager
    return mgr.get_all_statuses()
