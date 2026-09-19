# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas unitarias de gestión energética y DynamicPowerGovernor.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas del administrador de energía, gobernador dinámico y directivas Windows."""

from unittest.mock import MagicMock, patch

from core.power_mgr import (
    BALANCED_GUID,
    HIGH_PERFORMANCE_GUID,
    DynamicPowerGovernor,
    is_admin,
    restore_original_power_settings,
    setup_windows_environment,
)


def test_is_admin_returns_bool():
    """Valida que is_admin retorne un booleano sin lanzar excepciones."""
    res = is_admin()
    assert isinstance(res, bool)


def test_dynamic_power_governor_flow():
    """Valida que el gobernador eleve a Alto Rendimiento al iniciar streaming y restaure al finalizar."""
    governor = DynamicPowerGovernor()

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.get_active_scheme_guid", return_value=BALANCED_GUID),
        patch("core.power_mgr.set_active_scheme", return_value=True) as mock_set_active,
        patch("core.power_mgr.acquire_stay_awake", return_value=True) as mock_stay_awake,
        patch("core.power_mgr.release_stay_awake", return_value=True) as mock_release_awake,
    ):
        # 1. Iniciar primer stream
        governor.on_stream_started(1)
        assert mock_stay_awake.called
        mock_set_active.assert_called_with(HIGH_PERFORMANCE_GUID)
        assert governor._is_boosted is True
        assert governor._original_scheme == BALANCED_GUID

        # 2. Iniciar segundo stream (no debe volver a llamar set_active_scheme)
        mock_set_active.reset_mock()
        governor.on_stream_started(2)
        assert not mock_set_active.called

        # 3. Detener un stream (aún queda 1 activo -> no restaura todavía)
        governor.on_stream_stopped(1)
        assert not mock_release_awake.called
        assert not mock_set_active.called

        # 4. Detener todos los streams (0 activos -> restaura el original)
        governor.on_stream_stopped(0)
        assert mock_release_awake.called
        mock_set_active.assert_called_with(BALANCED_GUID)
        assert governor._is_boosted is False
        assert governor._original_scheme is None


def test_dynamic_power_governor_shutdown():
    """Valida que shutdown restaure el esquema original si estaba en modo de alto rendimiento."""
    governor = DynamicPowerGovernor()

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.get_active_scheme_guid", return_value=BALANCED_GUID),
        patch("core.power_mgr.set_active_scheme", return_value=True) as mock_set_active,
        patch("core.power_mgr.acquire_stay_awake", return_value=True),
        patch("core.power_mgr.release_stay_awake", return_value=True) as mock_release_awake,
    ):
        governor.on_stream_started(1)
        assert governor._is_boosted is True

        governor.shutdown()
        mock_set_active.assert_called_with(BALANCED_GUID)
        assert mock_release_awake.called
        assert governor._is_boosted is False


def test_setup_windows_environment_structure():
    """Valida que setup_windows_environment retorne una estructura de reporte válida."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = ""

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.backup_current_power_settings"),
        patch("core.power_mgr.get_active_scheme_guid", return_value=BALANCED_GUID),
        patch("core.power_mgr.set_active_scheme", return_value=True),
        patch("core.power_mgr.subprocess.run", return_value=mock_run),
        patch("core.power_mgr.is_admin", return_value=False),
    ):
        report = setup_windows_environment()
        assert "status" in report
        assert "applied" in report
        assert "failed" in report
        assert "warnings" in report
        assert report["status"] in ("ok", "partial", "failed")


def test_restore_original_power_settings_missing_backup():
    """Valida que restore_original_power_settings maneje la ausencia de archivo de respaldo adecuadamente."""
    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("os.path.exists", return_value=False),
    ):
        res = restore_original_power_settings()
        assert res["status"] == "error"
        assert "No se encontró respaldo" in res["message"]
