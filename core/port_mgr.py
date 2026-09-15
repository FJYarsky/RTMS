# ==============================================================================
# RTMS v2.2.2 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import socket
import logging
import threading
from typing import Optional, Set

logger = logging.getLogger("rtms.port_mgr")

class PortManager:
    """
    Gestor de asignación y reciclaje de puertos para transmisiones SRT/UDP.
    Verifica activamente la disponibilidad física del socket en el SO.
    Previene condiciones TOCTOU mediante revalidación previa al lanzamiento (P1-01).
    """
    DEFAULT_MIN_PORT = 9000
    DEFAULT_MAX_PORT = 9200

    def __init__(self, min_port: int = DEFAULT_MIN_PORT, max_port: int = DEFAULT_MAX_PORT):
        self.min_port = min_port
        self.max_port = max_port
        self._allocated_ports: Set[int] = set()
        self._lock = threading.Lock()

    def is_port_in_use(self, port: int) -> bool:
        """Verifica si un puerto está ocupado tanto en TCP como en UDP."""
        # Verificar UDP
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind(("0.0.0.0", port))
        except OSError:
            return True

        # Verificar TCP (por si algún otro servicio local lo está usando)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
        except OSError:
            return True

        return False

    def revalidate_port(self, port: int) -> bool:
        """Comprueba si el puerto previamente asignado sigue estando libre justo antes de usarlo."""
        return not self.is_port_in_use(port)

    def allocate_port(self, preferred_port: Optional[int] = None) -> int:
        """
        Asigna un puerto libre. Si preferred_port está libre y en rango, lo asigna.
        De lo contrario, busca secuencialmente en el rango configurado.
        """
        with self._lock:
            if preferred_port and self.min_port <= preferred_port <= self.max_port:
                if preferred_port not in self._allocated_ports and not self.is_port_in_use(preferred_port):
                    self._allocated_ports.add(preferred_port)
                    return preferred_port

            for port in range(self.min_port, self.max_port + 1):
                if port in self._allocated_ports:
                    continue
                if not self.is_port_in_use(port):
                    self._allocated_ports.add(port)
                    return port

            raise RuntimeError(f"No hay puertos libres disponibles en el rango {self.min_port}-{self.max_port}")

    def reallocate_if_collided(self, current_port: int) -> int:
        """Reasigna un nuevo puerto libre si ocurrió una colisión externa con current_port."""
        with self._lock:
            self._allocated_ports.discard(current_port)
        new_port = self.allocate_port()
        logger.warning(f"Colisión de puerto detectada en {current_port}. Reasignado a nuevo puerto libre: {new_port}")
        return new_port

    def release_port(self, port: int):
        """Libera un puerto previamente asignado."""
        with self._lock:
            self._allocated_ports.discard(port)

    def register_port(self, port: int):
        """Registra un puerto cargado desde configuración persistente."""
        with self._lock:
            self._allocated_ports.add(port)

# Instancia global única
port_manager = PortManager()
