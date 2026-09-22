# ==============================================================================
# RTMS — Real-Time Multicam System
# Paquete de persistencia transaccional ACID (SQLite WAL).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Capa de repositorio para persistencia transaccional con SQLite WAL."""

from core.repository.config_repository import ConfigRepository, config_repository
from core.repository.database import get_db_path, get_sync_connection, init_db
from core.repository.migrator import auto_migrate_json_to_sqlite, export_sqlite_to_json

__all__ = [
    "ConfigRepository",
    "config_repository",
    "get_db_path",
    "get_sync_connection",
    "init_db",
    "auto_migrate_json_to_sqlite",
    "export_sqlite_to_json",
]
