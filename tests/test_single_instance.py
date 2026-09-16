# ==============================================================================
# RTMS — Real-Time Multicam System
# Tests de prevención de instancias múltiples y señalización mediante Mutex de Windows
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

from core.single_instance import (
    acquire_single_instance_lock,
    release_single_instance_lock
)

def test_single_instance_lifecycle():
    """Valida que el mutex de instancia única pueda adquirirse y liberarse limpiamente."""
    # Asegurar estado limpio inicial
    release_single_instance_lock()

    # Adquirir mutex
    acquired = acquire_single_instance_lock()
    assert acquired is True

    # Liberar mutex
    release_single_instance_lock()

def test_double_release_is_safe():
    """Valida que liberar un mutex ya liberado o inexistente no arroje excepciones."""
    release_single_instance_lock()
    release_single_instance_lock()
