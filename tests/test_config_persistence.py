# ==============================================================================
# RTMS v2.0.4 — Tests Unitarios de Persistencia y Migraciones (core/config_mgr.py)
# ==============================================================================

import os
import core.config_mgr
from core.config_mgr import (
    migrate_config, save_config, load_config,
    generate_stable_camera_id
)

def test_generate_stable_camera_id_is_deterministic():
    """Valida que el camera_id generado para un mismo device_path sea determinista e idéntico."""
    dp = "@device_pnp_\\\\?\\usb#vid_04f2&pid_b604#123"
    id1 = generate_stable_camera_id(dp)
    id2 = generate_stable_camera_id(dp)

    assert id1 == id2
    assert id1.startswith("cam_")
    assert len(id1) >= 10

def test_migrate_config_v1_to_v3():
    """Valida la migración incremental de configuraciones antiguas a la versión actual."""
    legacy_data = {
        "cameras": {
            "@device_legacy_1": {
                "friendly_name": "Antigua Webcam",
                "resolution": "720p",
                "fps": 30,
                "bitrate": 2500
            }
        }
    }
    migrated = migrate_config(legacy_data)

    assert migrated["config_schema_version"] == 3
    cam = migrated["cameras"]["@device_legacy_1"]
    assert cam["protocol"] == "srt"
    assert "id" in cam
    assert cam["id"].startswith("cam_")
    assert "srt_passphrase" in cam
    assert len(cam["srt_passphrase"]) > 0

def test_config_atomic_save_and_backup_creation():
    """Valida que save_config genere tanto config.json como la copia de respaldo .bak."""
    test_data = load_config()
    test_data["test_marker"] = "rtms_persistence_test"
    save_config(test_data)

    assert os.path.exists(core.config_mgr.CONFIG_FILE)
    loaded = load_config()
    assert loaded.get("test_marker") == "rtms_persistence_test"

    # Segunda modificación para verificar la creación del archivo de respaldo .bak
    loaded["test_marker"] = "rtms_persistence_test_updated"
    save_config(loaded)
    assert os.path.exists(core.config_mgr.CONFIG_BAK_FILE)
    reloaded = load_config()
    assert reloaded.get("test_marker") == "rtms_persistence_test_updated"
