# ==============================================================================
# RTMS — Real-Time Multicam System
# Migrador atómico reversible de configuración (JSON a SQLite WAL).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Migrador automático desde config/config.json hacia config/rtms.db (SQLite WAL).
Crea un respaldo de seguridad inmutable y asegura que la transición sea
atómica y completamente transparente sin pérdida de datos.
"""

import json
import logging
import os
import shutil
from typing import Optional

from core.repository.config_repository import config_repository
from core.repository.database import get_db_path

logger = logging.getLogger("rtms.repository.migrator")


def auto_migrate_json_to_sqlite(
    json_path: Optional[str] = None,
    backup_suffix: str = ".v2.4.1.bak",
) -> bool:
    """
    Detecta si existe un config.json previo y lo migra hacia la base de datos SQLite WAL
    si la base de datos está vacía. Crea un backup previo inmutable.
    """
    db_path = get_db_path()
    if not json_path:
        json_path = os.path.join(os.path.dirname(db_path), "config.json")

    if not os.path.exists(json_path):
        logger.debug(f"No se encontró archivo JSON en '{json_path}'. Omitiendo migración inicial.")
        return False

    # Verificar si la base de datos ya contiene datos
    existing_cameras = config_repository.get_all_cameras_sync()
    existing_settings = config_repository.get_system_settings_sync()
    if existing_cameras or existing_settings:
        logger.debug("La base de datos SQLite ya contiene registros. Omitiendo migración desde JSON.")
        return False

    logger.info(f"Iniciando migración automática de configuración desde '{json_path}' hacia SQLite WAL...")
    try:
        # 1. Crear backup inmutable del archivo JSON original
        backup_path = f"{json_path}{backup_suffix}"
        if not os.path.exists(backup_path):
            shutil.copy2(json_path, backup_path)
            logger.info(f"Respaldo de seguridad creado exitosamente en '{backup_path}'.")

        # 2. Cargar datos del JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 3. Guardar transaccionalmente en la base de datos SQLite
        config_repository.save_full_config_sync(data)
        logger.info("Configuración migrada exitosamente a SQLite WAL.")
        return True
    except Exception as e:
        logger.exception(f"Error crítico durante la migración de JSON a SQLite: {e}")
        return False


def export_sqlite_to_json(target_path: Optional[str] = None) -> bool:
    """Exporta el estado completo de SQLite WAL hacia un archivo JSON como réplica."""
    db_path = get_db_path()
    if not target_path:
        target_path = os.path.join(os.path.dirname(db_path), "config.json")

    try:
        data = config_repository.load_full_config_sync()
        tmp_file = f"{target_path}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_file, target_path)
        logger.debug(f"Réplica JSON exportada exitosamente a '{target_path}'.")
        return True
    except Exception as e:
        logger.warning(f"No se pudo exportar réplica JSON de la configuración: {e}")
        return False
