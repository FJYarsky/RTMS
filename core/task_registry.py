# ==============================================================================
# RTMS — Real-Time Multicam System
# Registro centralizado y drenaje seguro de tareas asíncronas (Task Registry).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Registro centralizado de tareas asíncronas (asyncio.Task).
Supervisa tareas de fondo (watchdog, sondeo de hardware, telemetría)
y permite su cancelación y drenaje ordenado durante el ciclo de apagado.
"""

import asyncio
import logging
from typing import Coroutine, Optional, Set

logger = logging.getLogger("rtms.task_registry")


class TaskRegistry:
    """
    Gestiona el ciclo de vida de tareas en segundo plano en asyncio.
    Previene fugas de tareas y garantiza una cancelación limpia en shutdown.
    """

    def __init__(self) -> None:
        self._tasks: Set[asyncio.Task] = set()

    def register(self, task: asyncio.Task, name: Optional[str] = None) -> asyncio.Task:
        """
        Registra una tarea para supervisión de ciclo de vida.
        Se remueve automáticamente al completarse.
        """
        if name and hasattr(task, "set_name"):
            task.set_name(name)

        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def create_task(self, coro: Coroutine, name: Optional[str] = None) -> asyncio.Task:
        """Crea y registra una tarea asíncrona en un único paso atómico."""
        task = asyncio.create_task(coro)
        return self.register(task, name=name)

    @property
    def active_tasks(self) -> Set[asyncio.Task]:
        """Retorna el conjunto de tareas aún activas."""
        return {t for t in self._tasks if not t.done()}

    async def cancel_all(self, timeout: float = 3.0) -> None:
        """
        Cancela todas las tareas registradas activas y espera su terminación
        dentro de una ventana de tiempo controlada.
        """
        pending = [t for t in self._tasks if not t.done()]
        if not pending:
            return

        logger.info(f"Cancelando {len(pending)} tareas asíncronas registradas...")
        for task in pending:
            task.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
            logger.info("Todas las tareas asíncronas registradas fueron canceladas y drenadas exitosamente.")
        except asyncio.TimeoutError:
            logger.warning(f"Tiempo de espera agotado ({timeout}s) drenando tareas asíncronas. Forzando continuación.")
        finally:
            self._tasks.clear()


# Singleton global
task_registry = TaskRegistry()
