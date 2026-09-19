# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de persistencia en disco y migraciones de configuración.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de persistencia en disco y migraciones de configuración."""

import json
import os

import pytest

import core.config_mgr
from core.config_mgr import (
    LegacyConfigSchemaError,
    generate_stable_camera_id,
    load_config,
    migrate_config,
    save_config,
)


def test_generate_stable_camera_id_is_deterministic():
    """Valida que el camera_id generado para un mismo device_path sea determinista e idéntico."""
    dp = "@device_pnp_\\\\?\\usb#vid_04f2&pid_b604#123"
    id1 = generate_stable_camera_id(dp)
    id2 = generate_stable_camera_id(dp)

    assert id1 == id2
    assert id1.startswith("cam_")
    assert len(id1) >= 10


def test_migrate_config_rejects_legacy_schemas():
    """Valida que esquemas previos (< 4) sean rechazados con LegacyConfigSchemaError."""
    legacy_data = {
        "config_schema_version": 3,
        "cameras": {"@device_legacy_1": {"friendly_name": "Antigua Webcam", "resolution": "720p"}},
    }
    with pytest.raises(LegacyConfigSchemaError):
        migrate_config(legacy_data)

    legacy_v1 = {"config_schema_version": 1, "cameras": {}}
    with pytest.raises(LegacyConfigSchemaError):
        migrate_config(legacy_v1)


def test_migrate_config_valid_v4():
    """Valida la verificación exitosa de configuración con esquema 4."""
    valid_data = {
        "config_schema_version": 4,
        "cameras": {"@device_1": {"friendly_name": "Webcam 1", "protocol": "srt", "port": 9000}},
    }
    migrated = migrate_config(valid_data)
    assert migrated["config_schema_version"] == 4
    cam = migrated["cameras"]["@device_1"]
    assert "id" in cam
    assert cam["id"].startswith("cam_")


def test_load_config_backups_legacy_and_resets():
    """Valida que load_config detecte versiones previas (<4), cree el backup .legacy_v2_bak y resetee a v4."""
    legacy_payload = {
        "version": "2.2.6",
        "config_schema_version": 2,
        "cameras": {"@cam_old": {"friendly_name": "Old Cam"}},
    }
    with open(core.config_mgr.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(legacy_payload, f)

    loaded = load_config()
    assert loaded["config_schema_version"] == 4
    assert "@cam_old" not in loaded.get("cameras", {})
    assert os.path.exists(core.config_mgr.CONFIG_LEGACY_BAK_FILE)
    # Limpiar archivo legacy creado
    try:
        os.remove(core.config_mgr.CONFIG_LEGACY_BAK_FILE)
    except Exception:
        pass


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
