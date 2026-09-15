# ==============================================================================
# RTMS v2.2.1 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import ctypes
import logging
import threading
import time
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger("rtms.telemetry")


class GpuTelemetryReader:
    """
    Lector de telemetría de GPU de latencia ultra-baja (<1ms) utilizando NVML nativo vía ctypes.
    No requiere dependencias externas adicionales en Python y conmuta suavemente a modo seguro
    (available=False) si el sistema no posee GPU NVIDIA o controladores compatibles.
    """

    def __init__(self):
        self.available: bool = False
        self._nvml: Optional[ctypes.CDLL] = None
        self._device_handle: Optional[ctypes.c_void_p] = None
        self._gpu_name: Optional[str] = None
        self._lock = threading.Lock()
        self._init_nvml()

    def _init_nvml(self):
        """Intenta localizar e inicializar la biblioteca NVML nativa."""
        try:
            # Buscar nvml.dll en el PATH estándar de Windows
            self._nvml = ctypes.CDLL("nvml.dll")
            init_res = self._nvml.nvmlInit_v2()
            if init_res != 0:
                logger.debug(f"nvmlInit_v2 retornó código {init_res}. GPU no disponible.")
                return

            device_count = ctypes.c_uint()
            res_count = self._nvml.nvmlDeviceGetCount_v2(ctypes.byref(device_count))
            if res_count != 0 or device_count.value == 0:
                logger.debug("No se detectaron dispositivos GPU mediante NVML.")
                return

            # Obtener el primer dispositivo de procesamiento gráfico (GPU 0)
            handle = ctypes.c_void_p()
            res_dev = self._nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle))
            if res_dev != 0:
                logger.debug(f"Error obteniendo handle de GPU 0: {res_dev}")
                return

            self._device_handle = handle

            # Obtener nombre comercial del dispositivo
            name_buf = ctypes.create_string_buffer(96)
            if self._nvml.nvmlDeviceGetName(self._device_handle, name_buf, 96) == 0:
                self._gpu_name = name_buf.value.decode("utf-8", errors="ignore").strip()

            self.available = True
            logger.info(f"Telemetría GPU inicializada con éxito: {self._gpu_name}")
        except Exception as e:
            logger.debug(f"NVML no disponible en el sistema: {e}")
            self.available = False
            self._nvml = None
            self._device_handle = None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Retorna las métricas de uso de GPU en tiempo real.
        Si la GPU no está disponible o falla la lectura, retorna available=False con valores nulos.
        """
        if not self.available or not self._nvml or not self._device_handle:
            return {
                "available": False,
                "gpu_percent": None,
                "name": None,
                "memory_used_mb": None,
                "memory_total_mb": None,
            }

        with self._lock:
            try:
                class nvmlUtilization_t(ctypes.Structure):
                    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

                class nvmlMemory_t(ctypes.Structure):
                    _fields_ = [
                        ("total", ctypes.c_ulonglong),
                        ("free", ctypes.c_ulonglong),
                        ("used", ctypes.c_ulonglong),
                    ]

                util = nvmlUtilization_t()
                mem = nvmlMemory_t()

                res_util = self._nvml.nvmlDeviceGetUtilizationRates(self._device_handle, ctypes.byref(util))
                res_mem = self._nvml.nvmlDeviceGetMemoryInfo(self._device_handle, ctypes.byref(mem))

                if res_util == 0 and res_mem == 0:
                    return {
                        "available": True,
                        "gpu_percent": float(util.gpu),
                        "name": self._gpu_name,
                        "memory_used_mb": round(mem.used / (1024 * 1024), 1),
                        "memory_total_mb": round(mem.total / (1024 * 1024), 1),
                    }
            except Exception as e:
                logger.debug(f"Fallo transitorio al consultar métricas GPU: {e}")

        return {
            "available": True,
            "gpu_percent": None,
            "name": self._gpu_name,
            "memory_used_mb": None,
            "memory_total_mb": None,
        }


class NetworkTelemetryTracker:
    """
    Rastreador de tráfico de red en tiempo real.
    Calcula tasas instantáneas de subida y bajada a partir de los contadores I/O acumulados de psutil.
    Thread-safe y protegido contra valores atípicos y reinicio de contadores del sistema operativo.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_time = time.time()
        try:
            initial_io = psutil.net_io_counters()
            self._last_sent: int = initial_io.bytes_sent
            self._last_recv: int = initial_io.bytes_recv
        except Exception:
            self._last_sent = 0
            self._last_recv = 0

        self._rate_sent_kbps: float = 0.0
        self._rate_recv_kbps: float = 0.0

    def get_metrics(self) -> Dict[str, float]:
        """
        Retorna las tasas de tráfico de red calculadas en kilobits y megabits por segundo.
        """
        now = time.time()
        with self._lock:
            dt = now - self._last_time
            # Se requiere al menos 0.4s entre lecturas para calcular derivadas precisas
            if dt >= 0.4:
                try:
                    net = psutil.net_io_counters()
                    # Prevenir lecturas anómalas ante reinicio de adaptador o desborde de entero
                    delta_sent = max(0, net.bytes_sent - self._last_sent)
                    delta_recv = max(0, net.bytes_recv - self._last_recv)

                    self._rate_sent_kbps = (delta_sent * 8.0) / (dt * 1000.0)
                    self._rate_recv_kbps = (delta_recv * 8.0) / (dt * 1000.0)

                    self._last_sent = net.bytes_sent
                    self._last_recv = net.bytes_recv
                    self._last_time = now
                except Exception as e:
                    logger.debug(f"Error consultando contadores de red psutil: {e}")

            total_kbps = self._rate_sent_kbps + self._rate_recv_kbps
            return {
                "sent_kbps": round(self._rate_sent_kbps, 1),
                "recv_kbps": round(self._rate_recv_kbps, 1),
                "total_kbps": round(total_kbps, 1),
                "sent_mbps": round(self._rate_sent_kbps / 1000.0, 2),
                "recv_mbps": round(self._rate_recv_kbps / 1000.0, 2),
                "total_mbps": round(total_kbps / 1000.0, 2),
            }


class SystemTelemetryService:
    """
    Servicio global de telemetría de hardware, red y transmisiones activas.
    Combina métricas de procesador, memoria RAM, aceleración GPU y ancho de banda.
    """

    _instance = None

    def __init__(self):
        self.gpu_reader = GpuTelemetryReader()
        self.net_tracker = NetworkTelemetryTracker()

    @classmethod
    def get_instance(cls) -> "SystemTelemetryService":
        if cls._instance is None:
            cls._instance = SystemTelemetryService()
        return cls._instance

    def collect(self, active_streams_count: int = 0, total_bitrate_kbps: float = 0.0) -> Dict[str, Any]:
        """Recolecta y unifica el estado global de telemetría para el HUD."""
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        gpu_stats = self.gpu_reader.get_metrics()
        net_stats = self.net_tracker.get_metrics()

        return {
            # CPU y RAM existentes
            "cpu_percent": round(cpu_pct, 1),
            "memory_percent": round(mem.percent, 1),
            "memory_used_mb": round(mem.used / (1024 * 1024), 1),
            "memory_total_mb": round(mem.total / (1024 * 1024), 1),
            # Streams existentes
            "active_streams_count": active_streams_count,
            "total_bitrate_kbps": round(total_bitrate_kbps, 1),
            # Telemetría de GPU
            "gpu_available": gpu_stats["available"],
            "gpu_percent": gpu_stats["gpu_percent"],
            "gpu_name": gpu_stats["name"],
            "gpu_memory_used_mb": gpu_stats["memory_used_mb"],
            "gpu_memory_total_mb": gpu_stats["memory_total_mb"],
            # Telemetría de Red
            "net_sent_kbps": net_stats["sent_kbps"],
            "net_recv_kbps": net_stats["recv_kbps"],
            "net_total_kbps": net_stats["total_kbps"],
            "net_sent_mbps": net_stats["sent_mbps"],
            "net_recv_mbps": net_stats["recv_mbps"],
            "net_total_mbps": net_stats["total_mbps"],
        }


telemetry_service = SystemTelemetryService.get_instance()
