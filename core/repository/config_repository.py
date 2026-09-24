# ==============================================================================
# RTMS — Real-Time Multicam System
# Repositorio transaccional de configuración persistida (SQLite WAL).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Repositorio ACID para la persistencia de configuraciones de cámaras, ajustes de sistema
y dispositivos ignorados utilizando SQLite en modo Write-Ahead Logging (WAL).
"""

import json
import logging
from typing import Any, Dict, List, Optional

import aiosqlite

from core.__version__ import __version__
from core.repository.database import get_db_path, get_sync_connection, init_db

logger = logging.getLogger("rtms.repository.config")


class ConfigRepository:
    """
    Repositorio de configuración con soporte transaccional y concurrente.
    Ofrece métodos asíncronos y síncronos para interactuar con la base de datos.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or get_db_path()
        # Garantizar que las tablas existan
        init_db(self.db_path)

    # --------------------------------------------------------------------------
    # Operaciones Síncronas (Thread-Safe para módulos de fondo / DirectShow)
    # --------------------------------------------------------------------------

    def get_all_cameras_sync(self) -> Dict[str, Dict[str, Any]]:
        """Retorna todas las cámaras configuradas indexadas por device_path."""
        conn = get_sync_connection(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT device_path, id, friendly_name, resolution, fps, bitrate, encoder,
                       port, protocol, srt_latency, srt_passphrase, zerolatency, auto_start,
                       is_virtual, udp_mode, udp_host
                FROM cameras
                """
            )
            cameras: Dict[str, Dict[str, Any]] = {}
            for row in cursor.fetchall():
                cameras[row["device_path"]] = {
                    "id": row["id"],
                    "friendly_name": row["friendly_name"],
                    "resolution": row["resolution"],
                    "fps": row["fps"],
                    "bitrate": row["bitrate"],
                    "encoder": row["encoder"],
                    "port": row["port"],
                    "protocol": row["protocol"],
                    "srt_latency": row["srt_latency"],
                    "srt_passphrase": row["srt_passphrase"],
                    "zerolatency": bool(row["zerolatency"]),
                    "auto_start": bool(row["auto_start"]),
                    "is_virtual": bool(row["is_virtual"]) if "is_virtual" in row.keys() else False,
                    "udp_mode": row["udp_mode"] if "udp_mode" in row.keys() else "multicast",
                    "udp_host": row["udp_host"] if "udp_host" in row.keys() else "127.0.0.1",
                }
            return cameras
        finally:
            conn.close()

    def save_camera_sync(self, device_path: str, cam: Dict[str, Any]) -> None:
        """Inserta o actualiza una cámara de forma transaccional."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO cameras (
                        device_path, id, friendly_name, resolution, fps, bitrate, encoder,
                        port, protocol, srt_latency, srt_passphrase, zerolatency, auto_start,
                        is_virtual, udp_mode, udp_host, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(device_path) DO UPDATE SET
                        id=excluded.id,
                        friendly_name=excluded.friendly_name,
                        resolution=excluded.resolution,
                        fps=excluded.fps,
                        bitrate=excluded.bitrate,
                        encoder=excluded.encoder,
                        port=excluded.port,
                        protocol=excluded.protocol,
                        srt_latency=excluded.srt_latency,
                        srt_passphrase=excluded.srt_passphrase,
                        zerolatency=excluded.zerolatency,
                        auto_start=excluded.auto_start,
                        is_virtual=excluded.is_virtual,
                        udp_mode=excluded.udp_mode,
                        udp_host=excluded.udp_host,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        device_path,
                        cam.get("id", ""),
                        cam.get("friendly_name", ""),
                        cam.get("resolution", "1080p"),
                        int(cam.get("fps", 60)),
                        int(cam.get("bitrate", 6000)),
                        cam.get("encoder", "libx264"),
                        int(cam.get("port", 9000)),
                        cam.get("protocol", "srt"),
                        int(cam.get("srt_latency", 120)),
                        cam.get("srt_passphrase", ""),
                        1 if cam.get("zerolatency", True) else 0,
                        1 if cam.get("auto_start", False) else 0,
                        1 if cam.get("is_virtual", False) else 0,
                        cam.get("udp_mode", "multicast"),
                        cam.get("udp_host", "127.0.0.1"),
                    ),
                )
        finally:
            conn.close()

    def delete_camera_sync(self, device_path: str) -> bool:
        """Elimina una cámara de la base de datos."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                cur = conn.execute("DELETE FROM cameras WHERE device_path = ?", (device_path,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def get_system_settings_sync(self) -> Dict[str, Any]:
        """Retorna todos los ajustes generales del sistema."""
        conn = get_sync_connection(self.db_path)
        try:
            cur = conn.execute("SELECT key, value FROM system_settings")
            settings = {}
            for row in cur.fetchall():
                try:
                    settings[row["key"]] = json.loads(row["value"])
                except Exception:
                    settings[row["key"]] = row["value"]
            return settings
        finally:
            conn.close()

    def set_system_setting_sync(self, key: str, value: Any) -> None:
        """Guarda un ajuste de sistema serializado en JSON."""
        conn = get_sync_connection(self.db_path)
        try:
            val_str = json.dumps(value)
            with conn:
                conn.execute(
                    """
                    INSERT INTO system_settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, val_str),
                )
        finally:
            conn.close()

    def get_ignored_devices_sync(self) -> List[Dict[str, Any]]:
        """Retorna la lista estructurada de dispositivos ignorados."""
        conn = get_sync_connection(self.db_path)
        try:
            cur = conn.execute(
                "SELECT device_path, friendly_name, ignored_at FROM ignored_devices ORDER BY ignored_at DESC"
            )
            return [
                {
                    "device_path": row["device_path"],
                    "friendly_name": row["friendly_name"],
                    "ignored_at": row["ignored_at"],
                }
                for row in cur.fetchall()
            ]
        finally:
            conn.close()

    def add_ignored_device_sync(self, device_path: str, friendly_name: str) -> None:
        """Agrega un dispositivo a la tabla de ignorados."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO ignored_devices (device_path, friendly_name, ignored_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(device_path) DO UPDATE SET
                        friendly_name=excluded.friendly_name,
                        ignored_at=CURRENT_TIMESTAMP
                    """,
                    (device_path, friendly_name),
                )
        finally:
            conn.close()

    def remove_ignored_device_sync(self, device_path: str) -> bool:
        """Remueve un dispositivo de la lista de ignorados."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                cur = conn.execute("DELETE FROM ignored_devices WHERE device_path = ?", (device_path,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def clear_ignored_devices_sync(self) -> None:
        """Limpia todos los dispositivos ignorados."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                conn.execute("DELETE FROM ignored_devices")
        finally:
            conn.close()

    def is_device_ignored_sync(self, device_path: str) -> bool:
        """Determina si un dispositivo está ignorado."""
        conn = get_sync_connection(self.db_path)
        try:
            cur = conn.execute("SELECT 1 FROM ignored_devices WHERE device_path = ?", (device_path,))
            return cur.fetchone() is not None
        finally:
            conn.close()

    def load_full_config_sync(self) -> Dict[str, Any]:
        """Reconstruye el diccionario completo de configuración para total compatibilidad con el formato v4."""
        cameras = self.get_all_cameras_sync()
        settings = self.get_system_settings_sync()
        ignored = self.get_ignored_devices_sync()

        return {
            "version": __version__,
            "config_schema_version": 4,
            "cameras": cameras,
            "ignored_devices": ignored,
            "next_port": settings.get("next_port", 9000),
            "unattended_autostart": settings.get("unattended_autostart", False),
            "mediamtx_srt_port": settings.get("mediamtx_srt_port", 8890),
        }

    def save_full_config_sync(self, data: Dict[str, Any]) -> None:
        """Guarda un diccionario de configuración completo de forma transaccional."""
        conn = get_sync_connection(self.db_path)
        try:
            with conn:
                # 1. Guardar ajustes
                next_port = data.get("next_port", 9000)
                autostart = data.get("unattended_autostart", False)
                srt_port = data.get("mediamtx_srt_port", 8890)
                conn.execute(
                    "INSERT INTO system_settings (key, value) VALUES ('next_port', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(next_port),),
                )
                conn.execute(
                    "INSERT INTO system_settings (key, value) VALUES ('unattended_autostart', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(autostart),),
                )
                conn.execute(
                    "INSERT INTO system_settings (key, value) VALUES ('mediamtx_srt_port', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(srt_port),),
                )

                # 2. Reemplazar cámaras
                conn.execute("DELETE FROM cameras")
                for dp, cam in data.get("cameras", {}).items():
                    conn.execute(
                        """
                        INSERT INTO cameras (
                            device_path, id, friendly_name, resolution, fps, bitrate, encoder,
                            port, protocol, srt_latency, srt_passphrase, zerolatency, auto_start,
                            is_virtual, udp_mode, udp_host, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            dp,
                            cam.get("id", ""),
                            cam.get("friendly_name", ""),
                            cam.get("resolution", "1080p"),
                            int(cam.get("fps", 60)),
                            int(cam.get("bitrate", 6000)),
                            cam.get("encoder", "libx264"),
                            int(cam.get("port", 9000)),
                            cam.get("protocol", "srt"),
                            int(cam.get("srt_latency", 120)),
                            cam.get("srt_passphrase", ""),
                            1 if cam.get("zerolatency", True) else 0,
                            1 if cam.get("auto_start", False) else 0,
                            1 if cam.get("is_virtual", False) else 0,
                            cam.get("udp_mode", "multicast"),
                            cam.get("udp_host", "127.0.0.1"),
                        ),
                    )

                # 3. Dispositivos ignorados
                conn.execute("DELETE FROM ignored_devices")
                for item in data.get("ignored_devices", []):
                    if isinstance(item, dict):
                        dp = item.get("device_path", "")
                        fn = item.get("friendly_name", dp)
                    else:
                        dp = str(item)
                        fn = dp
                    if dp:
                        conn.execute(
                            "INSERT INTO ignored_devices (device_path, friendly_name) VALUES (?, ?)",
                            (dp, fn),
                        )
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Operaciones Asíncronas (aiosqlite) para endpoints de API
    # --------------------------------------------------------------------------

    async def get_all_cameras(self) -> Dict[str, Dict[str, Any]]:
        """Retorna todas las cámaras de forma asíncrona."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT device_path, id, friendly_name, resolution, fps, bitrate, encoder,
                       port, protocol, srt_latency, srt_passphrase, zerolatency, auto_start,
                       is_virtual, udp_mode, udp_host
                FROM cameras
                """
            )
            rows = await cursor.fetchall()
            cameras: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                cameras[row["device_path"]] = {
                    "id": row["id"],
                    "friendly_name": row["friendly_name"],
                    "resolution": row["resolution"],
                    "fps": row["fps"],
                    "bitrate": row["bitrate"],
                    "encoder": row["encoder"],
                    "port": row["port"],
                    "protocol": row["protocol"],
                    "srt_latency": row["srt_latency"],
                    "srt_passphrase": row["srt_passphrase"],
                    "zerolatency": bool(row["zerolatency"]),
                    "auto_start": bool(row["auto_start"]),
                    "is_virtual": bool(row["is_virtual"]) if "is_virtual" in row.keys() else False,
                    "udp_mode": row["udp_mode"] if "udp_mode" in row.keys() else "multicast",
                    "udp_host": row["udp_host"] if "udp_host" in row.keys() else "127.0.0.1",
                }
            return cameras

    async def get_ignored_devices(self) -> List[Dict[str, Any]]:
        """Retorna dispositivos ignorados de forma asíncrona."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT device_path, friendly_name, ignored_at FROM ignored_devices ORDER BY ignored_at DESC"
            )
            rows = await cursor.fetchall()
            return [
                {
                    "device_path": row["device_path"],
                    "friendly_name": row["friendly_name"],
                    "ignored_at": row["ignored_at"],
                }
                for row in rows
            ]

    async def add_ignored_device(self, device_path: str, friendly_name: str) -> None:
        """Agrega un dispositivo ignorado de forma asíncrona."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO ignored_devices (device_path, friendly_name, ignored_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(device_path) DO UPDATE SET
                    friendly_name=excluded.friendly_name,
                    ignored_at=CURRENT_TIMESTAMP
                """,
                (device_path, friendly_name),
            )
            await db.commit()

    async def remove_ignored_device(self, device_path: str) -> bool:
        """Remueve un dispositivo ignorado de forma asíncrona."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM ignored_devices WHERE device_path = ?", (device_path,))
            await db.commit()
            return cursor.rowcount > 0

    async def clear_ignored_devices(self) -> None:
        """Limpia dispositivos ignorados de forma asíncrona."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ignored_devices")
            await db.commit()


# Singleton global
config_repository = ConfigRepository()
