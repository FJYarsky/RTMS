# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas unitarias de cobertura exhaustiva para módulos core.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas sintéticas y de cobertura para power_mgr, system_env, preview_mgr, mediamtx_mgr."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.ffmpeg_tester import StreamDigestResult
from core.mediamtx_mgr import MediaMTXManager
from core.power_mgr import (
    acquire_stay_awake,
    backup_current_power_settings,
    get_power_setting,
    release_stay_awake,
    restore_original_power_settings,
)
from core.preview_mgr import PreviewManager
from core.system_env import (
    remove_firewall_rules,
    set_high_resolution_timer,
    setup_firewall_rules,
    unblock_app_binaries,
)


def test_power_mgr_get_power_setting_parsing():
    """Valida el análisis de cadenas AC y DC de la salida de powercfg."""
    sample_stdout = """
    Subgroup GUID: 238c27d7-2e2d-47d2-a56e-df0e11f6c163  (Sleep)
      Power Setting GUID: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (Standby after)
        Current AC Power Setting Index: 0x00000384
        Current DC Power Setting Index: 0x000001c2
    """
    mock_res = MagicMock()
    mock_res.stdout = sample_stdout
    mock_res.returncode = 0

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.subprocess.run", return_value=mock_res),
    ):
        ac, dc = get_power_setting("SUB_SLEEP", "STANDBYIDLE")
        assert ac == 0x384
        assert dc == 0x1C2


def test_power_mgr_backup_and_restore_cycle(tmp_path: Path):
    """Valida la creación atómica de backup_current_power_settings y su restauración."""
    backup_file = tmp_path / "power_backup.json"

    with (
        patch("core.power_mgr.sys.platform", "win32"),
        patch("core.power_mgr.BACKUP_FILE", str(backup_file)),
        patch("core.power_mgr.get_active_scheme_guid", return_value="8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"),
        patch("core.power_mgr.get_power_setting", return_value=(900, 450)),
        patch("core.power_mgr.get_hibernate_enabled", return_value=0),
        patch("core.power_mgr.get_net_adapters_pnp", return_value={"0001": 24}),
        patch("core.power_mgr.set_active_scheme", return_value=True),
        patch("core.power_mgr.subprocess.run") as mock_subproc,
    ):
        mock_subproc.return_value = MagicMock(returncode=0)

        # 1. Crear respaldo
        backup_current_power_settings()
        assert backup_file.exists()

        data = json.loads(backup_file.read_text(encoding="utf-8"))
        assert data["active_scheme_guid"] == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        assert data["timeouts"]["standby-timeout-ac"] == 900
        assert data["hibernate_enabled"] == 0

        # 2. Restaurar
        with patch("winreg.OpenKey"), patch("winreg.SetValueEx"):
            res = restore_original_power_settings()
            assert res["status"] == "ok"
            assert not backup_file.exists()


def test_power_mgr_stay_awake_win32():
    """Valida acquire_stay_awake y release_stay_awake bajo Windows."""
    with patch("core.power_mgr.sys.platform", "win32"):
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.SetThreadExecutionState.return_value = 0x80000001
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            assert acquire_stay_awake() is True
            assert release_stay_awake() is True

    with patch("core.power_mgr.sys.platform", "linux"):
        assert acquire_stay_awake() is False
        assert release_stay_awake() is False


def test_system_env_timer_resolution():
    """Valida configuración de resolución de temporizador timeBeginPeriod/timeEndPeriod."""
    with patch("core.system_env.sys.platform", "win32"):
        mock_ctypes = MagicMock()
        mock_ctypes.windll.winmm.timeBeginPeriod.return_value = 0
        mock_ctypes.windll.winmm.timeEndPeriod.return_value = 0
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            assert set_high_resolution_timer(True) is True
            assert set_high_resolution_timer(False) is True

    with patch("core.system_env.sys.platform", "linux"):
        assert set_high_resolution_timer(True) is False


def test_system_env_unblock_binaries(tmp_path: Path):
    """Valida eliminación de Zone.Identifier alternativos."""
    test_exe = tmp_path / "test.exe"
    test_exe.write_text("binary", encoding="utf-8")

    with (
        patch("core.system_env.sys.platform", "win32"),
        patch("core.system_env.get_base_dir", return_value=str(tmp_path)),
    ):
        # Si no hay streams ADS no falla
        cleaned = unblock_app_binaries()
        assert cleaned >= 0

    with patch("core.system_env.sys.platform", "linux"):
        assert unblock_app_binaries() == 0


def test_system_env_firewall_rules():
    """Valida add y remove firewall rules en Windows."""
    with (
        patch("core.system_env.sys.platform", "win32"),
        patch("core.system_env.is_admin", return_value=True),
        patch("core.system_env.subprocess.run") as mock_run,
    ):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        assert setup_firewall_rules("8889-8990,9000-9200") is True
        assert remove_firewall_rules() is True


def test_preview_mgr_ffplay_lifecycle():
    """Valida el ciclo de vida del visor flotante FFplay en PreviewManager."""
    pm = PreviewManager()
    assert pm.is_ffplay_running() is False

    with (
        patch("core.preview_mgr.has_ffmpeg_binary", return_value=True),
        patch("core.preview_mgr.get_ffplay_bin", return_value="ffplay.exe"),
        patch("core.preview_mgr.os.path.exists", return_value=True),
        patch("subprocess.Popen") as mock_popen,
    ):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        ok = pm.launch_ffplay("srt://127.0.0.1:8890?streamid=read:cam1", title="Test Monitor")
        assert ok is True
        assert pm.is_ffplay_running() is True

        pm.terminate_all_ffplay()
        assert mock_proc.terminate.called or mock_proc.kill.called


def test_mediamtx_mgr_config_and_ports(tmp_path: Path):
    """Valida generación de configuración, detección de puertos y rutas en MediaMTXManager."""
    mgr = MediaMTXManager()
    mock_base = tmp_path / "rtms_test"
    mock_base.mkdir(parents=True, exist_ok=True)

    with patch("core.mediamtx_mgr.get_base_dir", return_value=str(mock_base)):
        cfg_file = mgr.ensure_config_exists()
        assert os.path.exists(cfg_file)

        srt_port = mgr.get_srt_port()
        assert srt_port in (8890, 8554)

        webrtc_port = mgr.get_webrtc_port()
        assert webrtc_port in (8889, 8888)

        api_port = mgr.get_api_port()
        assert api_port == 9997


def test_stream_digest_result_formatting():
    """Valida el método summary y la propiedad is_success de StreamDigestResult."""
    # Éxito
    res_ok = StreamDigestResult(
        protocol="srt",
        url="srt://127.0.0.1:8890",
        is_connected=True,
        frames_decoded=150,
        detected_fps=30.0,
        real_fps=29.98,
        width=1920,
        height=1080,
        codec="h264",
    )
    assert res_ok.is_success is True
    summary_ok = res_ok.summary()
    assert "EXITOSA" in summary_ok
    assert "1920x1080" in summary_ok

    # Fallo con errores
    res_err = StreamDigestResult(
        protocol="udp",
        url="udp://127.0.0.1:9000",
        is_connected=False,
        frames_decoded=0,
        errors=["Connection timed out"],
    )
    assert res_err.is_success is False
    summary_err = res_err.summary()
    assert "FALLIDA" in summary_err
    assert "Connection timed out" in summary_err
