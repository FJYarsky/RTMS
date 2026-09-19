# ==============================================================================
# RTMS — Real-Time Multicam System
# Recolección y monitorización de métricas de rendimiento del sistema.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Monitorización en tiempo real de telemetría y rendimiento."""

import ctypes
import logging
import threading
import time
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger("rtms.telemetry")


# Definición de estructuras de datos ctypes a nivel de módulo para NVML
class nvmlUtilization_t(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

class nvmlMemory_t(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]

class GpuTelemetryReader:
    """
    Lector de telemetría de GPU de latencia ultra-baja (<1ms) utilizando NVML nativo vía ctypes.
    No requiere dependencias externas adicionales en Python y conmuta suavemente a modo seguro
    (available=False) si el sistema no posee GPU NVIDIA o controladores compatibles.
    """

    def __init__(self, device_index: int = 0):
        self.available: bool = False
        self.device_index = device_index
        self._nvml: Optional[ctypes.CDLL] = None
        self._nvml_initialized: bool = False
        self._device_handle: Optional[ctypes.c_void_p] = None
        self._gpu_name: Optional[str] = None
        self._consecutive_errors: int = 0
        self._lock = threading.Lock()
        self._init_nvml()

    def _init_nvml(self):
        """Intenta localizar e inicializar la biblioteca NVML nativa con manejo seguro de errores."""
        try:
            # Buscar nvml.dll en el PATH estándar de Windows
            self._nvml = ctypes.CDLL("nvml.dll")
            init_res = self._nvml.nvmlInit_v2()
            if init_res != 0:
                logger.debug(f"nvmlInit_v2 retornó código {init_res}. GPU no disponible.")
                return

            self._nvml_initialized = True

            device_count = ctypes.c_uint()
            res_count = self._nvml.nvmlDeviceGetCount_v2(ctypes.byref(device_count))
            if res_count != 0 or device_count.value == 0:
                logger.debug("No se detectaron dispositivos GPU mediante NVML.")
                self.shutdown()
                return

            # Obtener el dispositivo de procesamiento gráfico por índice
            handle = ctypes.c_void_p()
            res_dev = self._nvml.nvmlDeviceGetHandleByIndex_v2(self.device_index, ctypes.byref(handle))
            if res_dev != 0:
                logger.debug(f"Error obteniendo handle de GPU {self.device_index}: {res_dev}")
                self.shutdown()
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
            self.shutdown()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Retorna las métricas de uso de GPU en tiempo real (GPU general y motor NVENC).
        Si la GPU no está disponible o falla la lectura, conmuta a estado degradado.
        """
        if not self.available or not self._nvml or not self._device_handle:
            return {
                "available": False,
                "gpu_percent": None,
                "encoder_percent": None,
                "name": None,
                "memory_used_mb": None,
                "memory_total_mb": None,
            }

        with self._lock:
            try:
                util = nvmlUtilization_t()
                mem = nvmlMemory_t()

                res_util = self._nvml.nvmlDeviceGetUtilizationRates(self._device_handle, ctypes.byref(util))
                res_mem = self._nvml.nvmlDeviceGetMemoryInfo(self._device_handle, ctypes.byref(mem))

                if res_util == 0 and res_mem == 0:
                    self._consecutive_errors = 0

                    # Consulta de métricas del codificador por hardware NVENC si está disponible
                    encoder_percent = None
                    try:
                        if hasattr(self._nvml, "nvmlDeviceGetEncoderUtilization"):
                            enc_util = ctypes.c_uint()
                            sampling = ctypes.c_uint()
                            if self._nvml.nvmlDeviceGetEncoderUtilization(self._device_handle, ctypes.byref(enc_util), ctypes.byref(sampling)) == 0:
                                encoder_percent = float(enc_util.value)
                    except Exception:
                        pass

                    return {
                        "available": True,
                        "gpu_percent": float(util.gpu),
                        "encoder_percent": encoder_percent,
                        "name": self._gpu_name,
                        "memory_used_mb": round(mem.used / (1024 * 1024), 1),
                        "memory_total_mb": round(mem.total / (1024 * 1024), 1),
                    }
                else:
                    self._consecutive_errors += 1
            except Exception as e:
                self._consecutive_errors += 1
                logger.debug(f"Fallo transitorio al consultar métricas GPU: {e}")

            # Detección de fallos persistentes para desactivación automática
            if self._consecutive_errors >= 5:
                logger.warning("Desactivando telemetría de GPU tras 5 fallos consecutivos de NVML.")
                self.available = False

        return {
            "available": self.available,
            "gpu_percent": None,
            "encoder_percent": None,
            "name": self._gpu_name,
            "memory_used_mb": None,
            "memory_total_mb": None,
        }

    def shutdown(self):
        """Libera de forma ordenada los handles de NVML y apaga la biblioteca nativa."""
        with self._lock:
            if self._nvml and self._nvml_initialized:
                try:
                    self._nvml.nvmlShutdown()
                    logger.info("NVML finalizado ordenadamente.")
                except Exception as e:
                    logger.debug(f"Aviso al cerrar NVML: {e}")
                finally:
                    self._nvml_initialized = False
            self.available = False
            self._device_handle = None
            self._nvml = None


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
    _instance_lock = threading.Lock()

    def __init__(self):
        # Inicialización del contador de CPU para calibrar la primera lectura
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        self.gpu_reader = GpuTelemetryReader()
        self.net_tracker = NetworkTelemetryTracker()

    @classmethod
    def get_instance(cls) -> "SystemTelemetryService":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = SystemTelemetryService()
            return cls._instance

    def collect(self, active_streams_count: int = 0, total_bitrate_kbps: float = 0.0) -> Dict[str, Any]:
        """Recolecta y unifica el estado global de telemetría para el HUD y monitor de estado."""
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
            # RTMS Broadcast Output Bitrate
            "active_streams_count": active_streams_count,
            "total_bitrate_kbps": round(total_bitrate_kbps, 1),
            # Telemetría de GPU
            "gpu_available": gpu_stats["available"],
            "gpu_percent": gpu_stats["gpu_percent"],
            "gpu_encoder_percent": gpu_stats.get("encoder_percent"),
            "gpu_name": gpu_stats["name"],
            "gpu_memory_used_mb": gpu_stats["memory_used_mb"],
            "gpu_memory_total_mb": gpu_stats["memory_total_mb"],
            # Tráfico de red global del sistema operativo
            "net_system_total_kbps": net_stats["total_kbps"],
            "net_system_sent_kbps": net_stats["sent_kbps"],
            "net_system_recv_kbps": net_stats["recv_kbps"],
            # Claves de compatibilidad
            "net_sent_kbps": net_stats["sent_kbps"],
            "net_recv_kbps": net_stats["recv_kbps"],
            "net_total_kbps": net_stats["total_kbps"],
            "net_sent_mbps": net_stats["sent_mbps"],
            "net_recv_mbps": net_stats["recv_mbps"],
            "net_total_mbps": net_stats["total_mbps"],
        }

    def shutdown(self):
        """Cierra los subsistemas de telemetría y libera recursos asociados."""
        self.gpu_reader.shutdown()


telemetry_service = SystemTelemetryService.get_instance()
