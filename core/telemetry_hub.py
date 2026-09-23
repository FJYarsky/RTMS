# ==============================================================================
# RTMS — Real-Time Multicam System
# Hub WebSocket de Telemetría a 10 Hz y Notificaciones Reactivas.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Hub de distribución asíncrona de telemetría a 10 Hz y eventos reactivos por WebSocket."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Set

import psutil

from core.telemetry import telemetry_service

logger = logging.getLogger("rtms.telemetry_hub")


class TelemetryWebSocketHub:
    """
    Gestor centralizado de clientes WebSocket para distribución reactiva de telemetría.
    Ejecuta un bucle de muestreo a 10 Hz únicamente cuando hay clientes conectados,
    eliminando el consumo innecesario de CPU cuando el navegador está cerrado.
    """

    def __init__(self) -> None:
        self._clients: Set[Any] = set()
        self._lock = asyncio.Lock()
        self._ticker_task: Optional[asyncio.Task] = None
        self._running = False
        self._tick_counter: int = 0
        self._last_cpu: float = 0.0
        self._last_mem_pct: float = 0.0
        self._last_mem_used: float = 0.0
        self._last_mem_total: float = 0.0

    async def register(self, websocket: Any) -> None:
        """Registra un nuevo cliente WebSocket y arranca el ticker de 10 Hz si es el primero."""
        async with self._lock:
            self._clients.add(websocket)
            client_count = len(self._clients)
            logger.info(f"Cliente WebSocket de telemetría conectado. Total activos: {client_count}")
            if client_count == 1 and (self._ticker_task is None or self._ticker_task.done()):
                self._running = True
                self._ticker_task = asyncio.create_task(self._ticker_loop())

    async def unregister(self, websocket: Any) -> None:
        """Desregistra un cliente WebSocket y suspende el ticker si no quedan suscriptores."""
        async with self._lock:
            self._clients.discard(websocket)
            client_count = len(self._clients)
            logger.info(f"Cliente WebSocket desconectado. Restantes activos: {client_count}")
            if client_count == 0 and self._ticker_task and not self._ticker_task.done():
                self._running = False
                self._ticker_task.cancel()
                self._ticker_task = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Difunde un mensaje JSON a todos los clientes WebSocket conectados."""
        if not self._clients:
            return

        message = json.dumps(payload)
        dead_clients = set()

        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead_clients.add(ws)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    self._clients.discard(ws)
                if len(self._clients) == 0 and self._ticker_task and not self._ticker_task.done():
                    self._running = False
                    self._ticker_task.cancel()
                    self._ticker_task = None

    async def broadcast_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Envía inmediatamente un evento reactivo de cambio de estado a todos los clientes."""
        payload = {
            "type": "event",
            "event": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }
        await self.broadcast(payload)

    def notify_event_threadsafe(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Método seguro para llamar desde hilos secundarios o callbacks sincrónicos."""
        try:
            target_loop = loop or asyncio.get_event_loop()
            if target_loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_event(event_type, data), target_loop)
        except Exception as e:
            logger.debug(f"Aviso notificando evento threadsafe ({event_type}): {e}")

    async def _ticker_loop(self) -> None:
        """Bucle principal de telemetría a 10 Hz (100 ms)."""
        logger.debug("Iniciando ticker de telemetría a 10 Hz.")
        try:
            while self._running:
                start_time = time.monotonic()
                self._tick_counter += 1

                # 1. Muestreo de baja frecuencia (1 Hz, cada 10 ciclos) para métricas pesadas de CPU/RAM
                if self._tick_counter % 10 == 1:
                    try:
                        self._last_cpu = round(psutil.cpu_percent(interval=None), 1)
                        mem = psutil.virtual_memory()
                        self._last_mem_pct = round(mem.percent, 1)
                        self._last_mem_used = round(mem.used / (1024 * 1024), 1)
                        self._last_mem_total = round(mem.total / (1024 * 1024), 1)
                    except Exception as err:
                        logger.debug(f"Error consultando CPU/RAM: {err}")

                # 2. Métricas de alta frecuencia (10 Hz): GPU y Tráfico de Red
                gpu_stats = telemetry_service.gpu_reader.get_metrics()
                net_stats = telemetry_service.net_tracker.get_metrics()

                # 3. Métricas de flujos activos (FPS, Bitrate, Dropped Frames)
                from core.stream_manager import stream_manager

                statuses = stream_manager.get_all_statuses()
                stream_metrics = []
                total_bitrate = 0.0
                running_count = 0

                for s in statuses:
                    st = s.get("status", {})
                    is_running = st.get("state") == "running"
                    if is_running:
                        running_count += 1
                        total_bitrate += float(st.get("current_bitrate_kbps", 0.0))

                    stream_metrics.append(
                        {
                            "device_path": s.get("device_path"),
                            "friendly_name": s.get("friendly_name"),
                            "state": st.get("state"),
                            "fps": st.get("current_fps", 0.0),
                            "bitrate_kbps": st.get("current_bitrate_kbps", 0.0),
                            "speed": st.get("current_speed", "1.0x"),
                            "dropped_frames": st.get("current_dropped_frames", 0),
                            "total_frames": st.get("total_frames", 0),
                        }
                    )

                packet = {
                    "type": "telemetry",
                    "timestamp": time.time(),
                    "system": {
                        "cpu_percent": self._last_cpu,
                        "memory_percent": self._last_mem_pct,
                        "memory_used_mb": self._last_mem_used,
                        "memory_total_mb": self._last_mem_total,
                        "active_streams_count": running_count,
                        "total_bitrate_kbps": round(total_bitrate, 1),
                        "gpu_available": gpu_stats.get("available", False),
                        "gpu_percent": gpu_stats.get("gpu_percent"),
                        "gpu_encoder_percent": gpu_stats.get("encoder_percent"),
                        "gpu_name": gpu_stats.get("name"),
                        "gpu_memory_used_mb": gpu_stats.get("memory_used_mb"),
                        "net_system_total_kbps": net_stats.get("total_kbps", 0.0),
                        "net_system_sent_kbps": net_stats.get("sent_kbps", 0.0),
                        "net_system_recv_kbps": net_stats.get("recv_kbps", 0.0),
                    },
                    "streams": stream_metrics,
                }

                await self.broadcast(packet)

                # Mantener cadencia precisa de 100 ms (10 Hz)
                elapsed = time.monotonic() - start_time
                sleep_time = max(0.01, 0.1 - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error inesperado en ticker de telemetría: {e}")
        finally:
            self._running = False
            logger.debug("Ticker de telemetría a 10 Hz finalizado.")

    async def stop(self) -> None:
        """Detiene el hub y desconecta ordenadamente a todos los clientes."""
        self._running = False
        if self._ticker_task and not self._ticker_task.done():
            self._ticker_task.cancel()
            self._ticker_task = None

        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
            self._clients.clear()


telemetry_hub = TelemetryWebSocketHub()
