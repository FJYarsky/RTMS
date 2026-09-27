# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas exhaustivas de Fuzzing, Condiciones de Borde y Robustez Defensiva.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Suite de pruebas de estrés, fuzzing de payloads inválidos, inyección de caracteres,
condiciones de borde en red y gestión defensiva de configuraciones y entorno de sistema.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.command_builder import CommandBuilder, build_ffmpeg_command
from core.config_mgr import (
    ConfigPersistenceError,
    LegacyConfigSchemaError,
    UnsupportedConfigSchemaError,
    get_base_dir,
    load_config,
    migrate_config,
    save_config,
)
from core.port_mgr import PortManager
from core.system_env import (
    get_platform_details,
    remove_firewall_rules,
    set_high_resolution_timer,
    setup_firewall_rules,
    unblock_app_binaries,
)
from main import create_app

# Payloads de prueba para fuzzing
OVERSIZED_STRING = "A" * 15000
SQL_INJECTIONS = [
    "' OR '1'='1",
    "'; DROP TABLE cameras; --",
    "' UNION SELECT id, friendly_name, device_path FROM cameras --",
    "1; EXEC xp_cmdshell('calc.exe'); --",
]
SHELL_METACHAINT = [
    "; calc.exe",
    "& notepad.exe",
    "| dir",
    "`whoami`",
    "$(whoami)",
    "&& echo hacked",
    "; rm -rf /",
]
UNICODE_AND_EMOJIS = [
    "🎥 Transmisión en Vivo 🚀",
    "مرحبا بالعالم \u202e\u202d",
    "こんにちは世界 (マルチカメラ)",
    "Caméra_Étage_1_ñÑ!#$%^&*()_+",
    "\\x00\\x01\\x02\\xff\\xfe",
]


@pytest.fixture
def auth_client():
    token = "fuzz_test_secure_token_999"
    app = create_app(token=token)
    client = TestClient(app)
    return client, {"X-RTMS-Token": token}


# ==============================================================================
# 1. API FUZZING & BOUNDARY TESTS
# ==============================================================================


def test_api_fuzzing_stream_action_boundaries(auth_client):
    """Verifica que el endpoint /api/stream/action maneje y rechace payloads extremos y malformados."""
    client, headers = auth_client

    # 1. Acción no permitida
    res = client.post("/api/stream/action", headers=headers, json={"device_path": "cam1", "action": "explode"})
    assert res.status_code == 422

    # 2. String gigante en device_path
    res = client.post("/api/stream/action", headers=headers, json={"device_path": OVERSIZED_STRING, "action": "stop"})
    assert res.status_code in (200, 400, 404)

    # 3. Inyección SQL y shell metacharacters en device_path
    for sqli in SQL_INJECTIONS + SHELL_METACHAINT:
        res = client.post("/api/stream/action", headers=headers, json={"device_path": sqli, "action": "stop"})
        assert res.status_code in (200, 400, 404)

    # 4. Unicode y RTL overrides
    for text in UNICODE_AND_EMOJIS:
        res = client.post("/api/stream/action", headers=headers, json={"device_path": text, "action": "stop"})
        assert res.status_code in (200, 400, 404)

    # 5. Payload con tipos de datos erróneos
    res = client.post("/api/stream/action", headers=headers, json={"device_path": 12345, "action": ["invalid", "list"]})
    assert res.status_code == 422


def test_api_fuzzing_stream_config_boundaries(auth_client):
    """Verifica la validación defensiva de puertos, bitrates, fps y resoluciones en /api/stream/config."""
    client, headers = auth_client

    # 1. Puertos fuera de rango (0, 1, 1023, 65536, 70000, negativos)
    invalid_ports = [0, 1, 80, 1023, 65536, 70000, -1, -9999]
    for p in invalid_ports:
        res = client.post("/api/system/settings", headers=headers, json={"mediamtx_srt_port": p})
        assert res.status_code == 422, f"Puerto {p} debió ser rechazado con 422"

    # 2. Bitrates inválidos en /api/stream/config (ge=500, le=100000)
    invalid_bitrates = [-500, 0, 100, 499, 100001, 999999999]
    for b in invalid_bitrates:
        res = client.post("/api/stream/config", headers=headers, json={"device_path": "test_cam", "bitrate": b})
        assert res.status_code == 422, f"Bitrate {b} debió ser rechazado con 422"

    # 3. FPS inválidos (ge=1, le=120)
    for fps in [-30, 0, 121, 500]:
        res = client.post("/api/stream/config", headers=headers, json={"device_path": "test_cam", "fps": fps})
        assert res.status_code == 422, f"FPS {fps} debió ser rechazado con 422"

    # 4. Resoluciones no permitidas
    for res_val in ["0x0", "99999x99999", "invalid_res", "", "8K"]:
        res = client.post(
            "/api/stream/config", headers=headers, json={"device_path": "test_cam", "resolution": res_val}
        )
        assert res.status_code == 422, f"Resolución {res_val} debió ser rechazada con 422"

    # 5. Longitud de Passphrase SRT fuera del estándar (10 a 79 chars)
    short_pass = "short123"  # 8 chars < 10
    long_pass = "A" * 80  # 80 chars > 79
    res_short = client.post(
        "/api/stream/config", headers=headers, json={"device_path": "test_cam", "srt_passphrase": short_pass}
    )
    assert res_short.status_code == 422

    res_long = client.post(
        "/api/stream/config", headers=headers, json={"device_path": "test_cam", "srt_passphrase": long_pass}
    )
    assert res_long.status_code == 422


def test_api_fuzzing_config_import_and_export(auth_client):
    """Verifica que la importación de configuración rechace payloads corruptos o manipulados."""
    client, headers = auth_client

    # 1. Payload de importación que no es diccionario
    res = client.post("/api/config/import", headers=headers, json={"config_data": "not_a_dict"})
    assert res.status_code == 422

    # 2. Diccionario sin clave 'cameras'
    res = client.post("/api/config/import", headers=headers, json={"config_data": {"version": "2.8.0"}})
    assert res.status_code == 422

    # 3. Configuración con cámaras con puertos fuera de rango
    bad_cfg = {
        "version": "2.8.0",
        "config_schema_version": 4,
        "cameras": {
            "cam1": {
                "port": 999999,  # Fuera de rango
                "resolution": "720p",
                "fps": 30,
                "bitrate": 3000,
            }
        },
    }
    res = client.post("/api/config/import", headers=headers, json={"config_data": bad_cfg})
    assert res.status_code == 422


def test_api_fuzzing_preview_ticket_boundaries(auth_client):
    """Valida los límites de TTL y sanitización de entrada en /api/preview/ticket."""
    client, headers = auth_client

    # 1. TTL fuera de límites (ge=5, le=120)
    for ttl in [-10, 0, 4, 121, 9999]:
        res = client.post(
            "/api/preview/ticket", headers=headers, json={"device_path": "video=TestCam", "ttl_seconds": ttl}
        )
        assert res.status_code == 422

    # 2. Dispositivo con nombre gigante
    res = client.post("/api/preview/ticket", headers=headers, json={"device_path": OVERSIZED_STRING, "ttl_seconds": 30})
    assert res.status_code == 200
    assert "ticket" in res.json()


def test_api_v1_compatibility_and_not_found(auth_client):
    """Verifica que rutas inexistentes o no mapeadas devuelvan 404 limpio sin caídas ni trazas 500."""
    client, headers = auth_client
    endpoints = [
        "/api/v1/streams",
        "/api/v1/config",
        "/api/v1/system",
        "/api/nonexistent",
        "/api/v1/unknown?param=" + OVERSIZED_STRING,
    ]
    for ep in endpoints:
        res = client.get(ep, headers=headers)
        assert res.status_code in (404, 405)


# ==============================================================================
# 2. COMMAND BUILDER EXTREME & INVALID CONFIGURATIONS
# ==============================================================================


@pytest.mark.asyncio
async def test_command_builder_extreme_bitrates():
    """Valida que CommandBuilder procese de forma segura bitrates extremos (0, negativos, strings grandes)."""
    # 1. Bitrate 0
    cmd, url, enc = await CommandBuilder.build_command({"bitrate": 0, "resolution": "720p"})
    assert "-b:v" in cmd and "0k" in cmd

    # 2. Bitrate negativo (-100)
    cmd, url, enc = await CommandBuilder.build_command({"bitrate": -100, "resolution": "720p"})
    assert "-b:v" in cmd and "-100k" in cmd

    # 3. Bitrate como string con sufijo 'k' ('10000000k')
    cmd, url, enc = await CommandBuilder.build_command({"bitrate": "10000000k", "resolution": "720p"})
    assert "-b:v" in cmd and "10000000k" in cmd

    # 4. Bitrate inválido (None o no-numérico) cae a default 3000k
    cmd, url, enc = await CommandBuilder.build_command({"bitrate": "invalid_string", "resolution": "720p"})
    assert "-b:v" in cmd and "3000k" in cmd

    cmd_none, _, _ = await CommandBuilder.build_command({"bitrate": None, "resolution": "720p"})
    assert "-b:v" in cmd_none and "3000k" in cmd_none


@pytest.mark.asyncio
async def test_command_builder_extreme_resolutions():
    """Valida que resoluciones inválidas, vacías o numéricas fuera de rango se manejen con fallbacks seguros."""
    test_cases = ["", "0x0", "99999x99999", "invalid", None]
    for r in test_cases:
        cmd, url, enc = await build_ffmpeg_command({"resolution": r, "bitrate": 2000})
        # Si la resolución no coincide con RESOLUTION_MAP, cae por defecto a 1280x720
        assert "-video_size" in cmd
        idx = cmd.index("-video_size")
        assert cmd[idx + 1] == "1280x720"


@pytest.mark.asyncio
async def test_command_builder_codecs_and_presets():
    """Valida que códecs desconocidos, presets y cadenas vacías se manejen sin excepciones no controladas."""
    # 1. Códec desconocido: se inyecta directamente a -c:v sin romper
    cmd, url, enc = await CommandBuilder.build_command({"encoder": "unknown_custom_codec"})
    assert "-c:v" in cmd
    assert "unknown_custom_codec" in cmd

    # 2. Códec vacío o None: cae a libx264 de forma segura
    cmd, url, enc = await CommandBuilder.build_command({"encoder": ""})
    assert "-c:v" in cmd and "libx264" in cmd

    cmd_none, url, enc = await CommandBuilder.build_command({"encoder": None})
    assert "-c:v" in cmd_none and "libx264" in cmd_none

    # 3. Codificadores hardware (NVENC, AMF, QSV)
    for hw_enc in ["h264_nvenc", "h264_amf", "h264_qsv", "av1_nvenc"]:
        cmd, url, enc = await CommandBuilder.build_command({"encoder": hw_enc, "zerolatency": True})
        assert "-c:v" in cmd and hw_enc in cmd


@pytest.mark.asyncio
async def test_command_builder_shell_metacharacters_in_device_path():
    """Valida que caracteres peligrosos en device_path no rompan la estructura de argumentos FFmpeg."""
    malicious_path = "@device:pnp:\\\\?\\usb#vid_1234&pid_5678#;calc.exe&dir|whoami"
    cmd, url, enc = await CommandBuilder.build_command({"device_path": malicious_path})
    assert any(malicious_path.replace(":", "\\:") in arg for arg in cmd)


@pytest.mark.asyncio
async def test_command_builder_udp_and_broadcast_profiles():
    """Valida la construcción de comandos con protocolo UDP y perfiles estándar sin zerolatency."""
    # 1. Protocolo UDP con libx265
    cmd_udp, url_udp, _ = await CommandBuilder.build_command(
        {
            "protocol": "udp",
            "port": 9055,
            "udp_mode": "multicast",
            "udp_host": "239.0.0.1",
            "encoder": "libx265",
            "zerolatency": False,
        }
    )
    assert "udp://" in url_udp and ":9055" in url_udp
    assert "-muxdelay" not in cmd_udp
    assert "-c:v" in cmd_udp and "libx265" in cmd_udp

    # 2. AMF y QSV sin zerolatency
    cmd_amf, _, _ = await CommandBuilder.build_command(
        {
            "encoder": "h264_amf",
            "zerolatency": False,
        }
    )
    assert "-quality" in cmd_amf and "balanced" in cmd_amf

    cmd_qsv, _, _ = await CommandBuilder.build_command(
        {
            "encoder": "h264_qsv",
            "zerolatency": False,
        }
    )
    assert "-preset" in cmd_qsv and "medium" in cmd_qsv


# ==============================================================================
# 3. PORT MANAGER EXHAUSTION & THREAD CONCURRENCY
# ==============================================================================


def test_port_manager_range_exhaustion():
    """Valida que PortManager detecte y maneje limpiamente el agotamiento total del rango."""
    pm = PortManager(min_port=9500, max_port=9502)

    with patch.object(pm, "is_port_in_use", return_value=False):
        p1 = pm.allocate_port()
        p2 = pm.allocate_port()
        p3 = pm.allocate_port()
        assert {p1, p2, p3} == {9500, 9501, 9502}

        # El cuarto intento debe levantar RuntimeError indicando agotamiento
        with pytest.raises(RuntimeError, match="No hay puertos libres disponibles"):
            pm.allocate_port()


def test_port_manager_release_and_reallocation_idempotency():
    """Valida la idempotencia de liberación y re-asignación de puertos."""
    pm = PortManager(min_port=9600, max_port=9610)

    with patch.object(pm, "is_port_in_use", return_value=False):
        port = pm.allocate_port()
        assert port == 9600

        # Liberar repetidamente no debe causar error
        pm.release_port(port)
        pm.release_port(port)
        pm.release_port(port)
        pm.release_port(9999)  # Puerto nunca asignado

        # Re-asignación exitosa del mismo puerto
        reallocated = pm.allocate_port()
        assert reallocated == 9600


def test_port_manager_concurrent_allocation_multithreaded():
    """Valida que múltiples hilos concurrentes reserven puertos únicos sin colisiones por condición de carrera."""
    total_threads = 25
    pm = PortManager(min_port=9700, max_port=9700 + total_threads + 10)

    allocated_ports = []

    def _worker():
        with patch.object(pm, "is_port_in_use", return_value=False):
            p = pm.allocate_port()
            allocated_ports.append(p)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_worker) for _ in range(total_threads)]
        for f in futures:
            f.result()

    assert len(allocated_ports) == total_threads
    assert len(set(allocated_ports)) == total_threads, "No deben existir puertos duplicados asignados concurrentemente"


def test_port_manager_preferred_port_and_socket_check():
    """Valida la asignación de puerto preferido y detección física de socket ocupado."""
    pm = PortManager(min_port=9300, max_port=9310)

    # 1. Asignar puerto preferido libre
    with patch.object(pm, "is_port_in_use", return_value=False):
        assigned = pm.allocate_port(preferred_port=9305)
        assert assigned == 9305

        # 2. Si el preferido ya está asignado o ocupado, debe tomar el siguiente libre del rango
        fallback = pm.allocate_port(preferred_port=9305)
        assert fallback != 9305
        assert 9300 <= fallback <= 9310

    # 3. Comprobación real de socket libre/ocupado
    assert isinstance(pm.is_port_in_use(65530), bool)
    assert isinstance(pm.revalidate_port(65530), bool)


# ==============================================================================
# 4. SYSTEM ENV & CONFIG MANAGER RESILIENCE
# ==============================================================================


def test_config_manager_corrupted_json_recovery(tmp_path):
    """Valida que un config.json dañado o corrupto se recupere desde backup o se reinicialice a default."""
    cfg_dir = tmp_path / "custom_config_dir"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.json"
    bak_file = cfg_dir / "config.json.bak"

    # 1. Escribir JSON corrupto (caracteres aleatorios que no parsean)
    cfg_file.write_text("{CORRUPTED_JSON_DATA!!!@@@###", encoding="utf-8")

    # 2. Configuración válida en backup
    valid_backup = {
        "version": "2.8.0",
        "config_schema_version": 4,
        "cameras": {"cam_bak": {"port": 9010, "friendly_name": "Backup Cam"}},
    }
    bak_file.write_text(json.dumps(valid_backup), encoding="utf-8")

    with (
        patch("core.config_mgr.CONFIG_DIR", str(cfg_dir)),
        patch("core.config_mgr.CONFIG_FILE", str(cfg_file)),
        patch("core.config_mgr.CONFIG_BAK_FILE", str(bak_file)),
        patch("core.repository.migrator.export_sqlite_to_json", return_value=False),
    ):
        loaded = load_config()
        assert "cam_bak" in loaded.get("cameras", {})


def test_config_manager_schema_migration_boundaries():
    """Valida el rechazo de esquemas heredados descontinuados (<4) y esquemas desconocidos futuros (>4)."""
    # 1. Esquema heredado (< 4)
    with pytest.raises(LegacyConfigSchemaError):
        migrate_config({"config_schema_version": 3, "cameras": {}})

    # 2. Esquema futuro no soportado (> 4)
    with pytest.raises(UnsupportedConfigSchemaError):
        migrate_config({"config_schema_version": 99, "cameras": {}})


def test_config_manager_file_permission_error_simulation(tmp_path):
    """Valida que errores de permisos en disco se manejen defensivamente (retornando False o levantando ConfigPersistenceError)."""
    cfg_dir = tmp_path / "perm_config_dir"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.json"

    dummy_cfg = {"version": "2.8.0", "config_schema_version": 4, "cameras": {}}

    with (
        patch("core.config_mgr.CONFIG_DIR", str(cfg_dir)),
        patch("core.config_mgr.CONFIG_FILE", str(cfg_file)),
        patch("os.replace", side_effect=PermissionError("Acceso denegado simulado")),
    ):
        # 1. Modo por defecto seguro: retorna False sin tumbar el hilo
        success = save_config(dummy_cfg, raise_on_error=False)
        assert success is False

        # 2. Modo explícito con raise_on_error=True: levanta ConfigPersistenceError
        with pytest.raises(ConfigPersistenceError, match="Fallo de persistencia en disco"):
            save_config(dummy_cfg, raise_on_error=True)


def test_config_manager_missing_directory_auto_creation(tmp_path):
    """Valida que si la carpeta de configuración no existe, se cree automáticamente."""
    missing_dir = tmp_path / "deep" / "nested" / "config"
    cfg_file = missing_dir / "config.json"
    bak_file = missing_dir / "config.json.bak"

    assert not missing_dir.exists()

    with (
        patch("core.config_mgr.CONFIG_DIR", str(missing_dir)),
        patch("core.config_mgr.CONFIG_FILE", str(cfg_file)),
        patch("core.config_mgr.CONFIG_BAK_FILE", str(bak_file)),
    ):
        loaded = load_config()
        assert missing_dir.exists()
        assert loaded["config_schema_version"] == 4


def test_config_manager_get_base_dir_fallback():
    """Valida el fallback seguro de get_base_dir cuando el directorio principal no es escribible."""
    with patch("builtins.open", side_effect=PermissionError("Directorio protegido")):
        bdir = get_base_dir()
        assert "RTMS" in bdir or os.path.exists(bdir)


def test_system_env_high_resolution_timer():
    """Valida la activación y desactivación segura del temporizador de 1 ms."""
    res_enable = set_high_resolution_timer(True)
    res_disable = set_high_resolution_timer(False)
    assert isinstance(res_enable, bool)
    assert isinstance(res_disable, bool)


def test_system_env_unblock_binaries():
    """Valida que unblock_app_binaries retorne la cuenta de archivos procesados sin lanzar excepciones."""
    count = unblock_app_binaries()
    assert isinstance(count, int)
    assert count >= 0


def test_system_env_firewall_rules_mock():
    """Valida el manejo defensivo en setup y remove de reglas de Firewall ante fallos o falta de privilegios."""
    # 1. Sin privilegios de admin
    with patch("core.system_env.is_admin", return_value=False):
        assert setup_firewall_rules() is False

    # 2. Con privilegios pero netsh falla
    mock_fail = MagicMock(returncode=1, stderr="Error de acceso", stdout="")
    with (
        patch("core.system_env.is_admin", return_value=True),
        patch("subprocess.run", return_value=mock_fail),
    ):
        assert setup_firewall_rules() is False

    # 3. Eliminación de reglas
    mock_ok = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_ok):
        assert remove_firewall_rules() is True


def test_system_env_platform_details():
    """Valida que get_platform_details devuelva un resumen completo del sistema operativo."""
    details = get_platform_details()
    assert "os" in details
    assert "edition" in details
    assert "arch" in details
    assert "summary" in details
    assert len(details["summary"]) > 0
