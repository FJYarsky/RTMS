# ==============================================================================
# RTMS v2.2.2 — Tests Unitarios para PortManager (core/port_mgr.py)
# ==============================================================================

import socket
from core.port_mgr import PortManager

def test_port_allocation_in_range():
    """Valida que los puertos se asignen dentro del rango permitido."""
    mgr = PortManager(min_port=9150, max_port=9160)
    p1 = mgr.allocate_port()
    p2 = mgr.allocate_port()

    assert 9150 <= p1 <= 9160
    assert 9150 <= p2 <= 9160
    assert p1 != p2

def test_port_release_and_reuse():
    """Valida que un puerto liberado pueda ser reasignado posteriormente."""
    mgr = PortManager(min_port=9180, max_port=9182)
    p1 = mgr.allocate_port()
    _ = mgr.allocate_port()

    mgr.release_port(p1)
    p3 = mgr.allocate_port()

    # p3 debe haber reutilizado p1 o el siguiente disponible
    assert p3 in (p1, 9182)

def test_detect_port_in_use():
    """Valida que PortManager detecte si un socket ya está enlazado por el SO."""
    mgr = PortManager()
    # Abrir un socket local temporal
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", 9199))
        assert mgr.is_port_in_use(9199) is True

    # Tras cerrar, el puerto debe figurar como libre
    assert mgr.is_port_in_use(9199) is False
