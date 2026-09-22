# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de prevención de instancias múltiples de la aplicación.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de prevención de instancias múltiples de la aplicación."""

from core.single_instance import acquire_single_instance_lock, release_single_instance_lock


def test_single_instance_lifecycle():
    """Valida que el mutex de instancia única pueda adquirirse y liberarse limpiamente."""
    test_mutex = "RTMS_UnitTest_Isolated_Mutex"
    # Asegurar estado limpio inicial
    release_single_instance_lock()

    # Adquirir mutex
    acquired = acquire_single_instance_lock(mutex_name=test_mutex)
    assert acquired is True

    # Liberar mutex
    release_single_instance_lock()


def test_double_release_is_safe():
    """Valida que liberar un mutex ya liberado o inexistente no arroje excepciones."""
    release_single_instance_lock()
    release_single_instance_lock()
