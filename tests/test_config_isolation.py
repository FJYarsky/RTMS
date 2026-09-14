import os
import asyncio
import core.config_mgr
from core.config_mgr import save_config, load_config, export_config
from core.hardware import hardware_detector

def test_config_isolated_from_production():
    # Verify that core.config_mgr.CONFIG_FILE points to a temporary pytest path and not the project root config.json
    real_prod_config = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json"))
    current_cfg = core.config_mgr.CONFIG_FILE
    assert os.path.abspath(current_cfg) != real_prod_config
    assert "pytest" in current_cfg or "tmp" in current_cfg or "temp" in current_cfg.lower()

def test_save_and_load_isolated():
    cfg = load_config()
    cfg["test_isolation_key"] = "verified"
    save_config(cfg)

    reloaded = load_config()
    assert reloaded.get("test_isolation_key") == "verified"

def test_export_config_safe_mode():
    cfg = {
        "version": "2.1.0",
        "cameras": {
            "cam1": {
                "friendly_name": "Camera 1",
                "srt_passphrase": "SuperSecretPassphrase123!",
                "port": 9000
            }
        }
    }
    save_config(cfg)

    # safe_mode=True should mask passphrase
    exported_safe = export_config(safe_mode=True)
    cam1_safe = exported_safe["cameras"]["cam1"]
    assert cam1_safe["srt_passphrase"] == "••••••••"
    assert cam1_safe["has_passphrase"] is True

    # safe_mode=False should preserve or reveal passphrase
    exported_raw = export_config(safe_mode=False)
    cam1_raw = exported_raw["cameras"]["cam1"]
    assert cam1_raw["srt_passphrase"] == "SuperSecretPassphrase123!"

def test_hardware_detector_cached():
    encs1 = asyncio.run(hardware_detector.get_available_encoders())
    encs2 = asyncio.run(hardware_detector.get_available_encoders())
    assert encs1 == encs2
    assert "libx264" in encs1
