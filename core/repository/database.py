# ==============================================================================
# RTMS — Real-Time Multicam System
# Motor de base de datos SQLite en modo WAL transaccional (ACID).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Inicialización y gestión del motor SQLite con Write-Ahead Logging (WAL).
Garantiza transaccionalidad ACID, soporte contra caídas intempestivas y
concurrencia segura entre lecturas y escrituras.
"""

import logging
import os
import sqlite3
from typing import Optional

from core.power_mgr import get_base_dir

logger = logging.getLogger("rtms.repository.db")

_DB_DIR = os.path.join(get_base_dir(), "config")
_DB_PATH = os.path.join(_DB_DIR, "rtms.db")

CURRENT_DB_SCHEMA_VERSION = 1

INIT_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    device_path TEXT PRIMARY KEY,
    id TEXT NOT NULL,
    friendly_name TEXT NOT NULL,
    resolution TEXT NOT NULL,
    fps INTEGER NOT NULL,
    bitrate INTEGER NOT NULL,
    encoder TEXT NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'srt',
    srt_latency INTEGER NOT NULL DEFAULT 120,
    srt_passphrase TEXT DEFAULT '',
    zerolatency INTEGER NOT NULL DEFAULT 1,
    auto_start INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ignored_devices (
    device_path TEXT PRIMARY KEY,
    friendly_name TEXT NOT NULL,
    ignored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_path() -> str:
    """Retorna la ruta absoluta a la base de datos SQLite."""
    return _DB_PATH


def get_sync_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Retorna una conexión síncrona thread-safe configurada en modo WAL con busy_timeout=5000.
    Utilizada en contextos síncronos (pystray, tareas DirectShow).
    """
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Inicializa el esquema de la base de datos si no existe."""
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = get_sync_connection(path)
    try:
        with conn:
            conn.executescript(INIT_SCHEMA_SQL)
            # Registrar versión de esquema si no está presente
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (CURRENT_DB_SCHEMA_VERSION,))
            if not cur.fetchone():
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (CURRENT_DB_SCHEMA_VERSION,))
        logger.info(f"Base de datos SQLite WAL inicializada correctamente en '{path}'.")
    except Exception as e:
        logger.error(f"Error inicializando base de datos SQLite en '{path}': {e}")
        raise
    finally:
        conn.close()
