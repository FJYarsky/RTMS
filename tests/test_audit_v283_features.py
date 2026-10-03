# ==============================================================================
# RTMS — Real-Time Multicam System
# Suite de pruebas automatizadas de validación y regresión para versión 2.8.3.
# Verifica todas las características, correcciones de bugs y criterios de aceptación.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias y de integración para las características de RTMS v2.8.3."""

import json
import os
import tomllib

import pytest

from api.schemas import CameraConfigUpdate, CameraPersistedConfig
from core.__version__ import __version__
from core.command_builder import build_ffmpeg_command
from core.config_mgr import CAMERA_PRESETS, get_or_allocate_camera_config
from core.mediamtx_mgr import mediamtx_manager
from core.process_optimizer import elevate_process_priority, get_pcore_affinity_mask
from core.repository.database import CURRENT_DB_SCHEMA_VERSION, INIT_SCHEMA_SQL, get_sync_connection, run_migrations
from core.stream_proc import build_client_urls, generate_rtp_sdp, generate_vlc_xspf_playlist
from core.uvc_control import lock_uvc_auto_exposure


def test_v283_version_bump_consistency():
    """Valida que la versión 2.8.3 esté sincronizada en __version__.py, pyproject.toml y config.example.json."""
    assert __version__ == "2.8.3"

    pyproject_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
    assert pyproject_data["project"]["version"] == "2.8.3"

    config_ex_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.example.json"
    )
    with open(config_ex_path, "r", encoding="utf-8") as f:
        config_ex = json.load(f)
    assert config_ex["version"] == "2.8.3"


def test_v283_database_migration_v3_default_fps(tmp_path):
    """Valida que la migración v3 fije 60 FPS por defecto y actualice cámaras previas a 60 FPS."""
    assert CURRENT_DB_SCHEMA_VERSION >= 3
    assert "fps INTEGER NOT NULL DEFAULT 60" in INIT_SCHEMA_SQL

    db_path = str(tmp_path / "test_migration_v3.db")
    conn = get_sync_connection(db_path)

    # Simular base de datos preexistente en versión 2 con cámara a 30 FPS
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("INSERT INTO schema_migrations (version) VALUES (2);")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            device_path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            resolution TEXT NOT NULL DEFAULT '720p',
            fps INTEGER NOT NULL DEFAULT 30,
            bitrate INTEGER NOT NULL DEFAULT 3000,
            protocol TEXT NOT NULL DEFAULT 'srt',
            encoder TEXT NOT NULL DEFAULT 'auto',
            srt_latency INTEGER NOT NULL DEFAULT 120,
            srt_passphrase TEXT,
            autostart INTEGER NOT NULL DEFAULT 0,
            zerolatency INTEGER NOT NULL DEFAULT 1,
            is_virtual INTEGER NOT NULL DEFAULT 0,
            udp_host TEXT NOT NULL DEFAULT '127.0.0.1',
            udp_mode TEXT NOT NULL DEFAULT 'unicast',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        INSERT INTO cameras (device_path, name, fps, protocol)
        VALUES ('cam_legacy', 'Camara 30fps', 30, 'udp');
    """)
    conn.commit()

    # Ejecutar migraciones sobre la conexión
    run_migrations(conn)

    # Verificar que la cámara fue actualizada a 60 FPS y la versión de esquema es 3
    cur = conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;")
    ver = cur.fetchone()["version"]
    assert ver >= 3

    cur = conn.execute("SELECT fps FROM cameras WHERE device_path = 'cam_legacy';")
    fps = cur.fetchone()["fps"]
    assert fps == 60
    conn.close()


def test_v283_config_presets_standard_60fps_and_unicast():
    """Valida que los presets de cámara estén estandarizados a 60 FPS y UDP unicast."""
    for preset in CAMERA_PRESETS.values():
        assert preset["fps"] == 60
        assert preset["protocol"] == "udp"
        assert preset["udp_mode"] == "unicast"

    # Asignación por defecto de cámara nueva
    cfg = get_or_allocate_camera_config("video=TestCam", "TestCam")
    assert cfg.get("fps") == 60
    assert cfg.get("protocol") == "udp"
    assert cfg.get("udp_mode") == "unicast"


def test_v283_pydantic_schema_unicast_persistence_and_rtp():
    """Valida que los schemas Pydantic acepten udp_host, udp_mode, protocol='udp' y protocol='rtp'."""
    update_data = {
        "device_path": "video=Webcam01",
        "protocol": "udp",
        "udp_host": "192.168.1.150",
        "udp_mode": "unicast",
        "fps": 60,
    }
    req = CameraConfigUpdate(**update_data)
    assert req.device_path == "video=Webcam01"
    assert req.protocol == "udp"
    assert req.udp_host == "192.168.1.150"
    assert req.udp_mode == "unicast"

    # Soporte para RTP
    rtp_req = CameraConfigUpdate(device_path="video=Webcam02", protocol="rtp", udp_host="192.168.1.200")
    assert rtp_req.protocol == "rtp"

    # Default de persistencia a 60 FPS
    persisted = CameraPersistedConfig(
        device_path="test_cam",
        name="Test",
    )
    assert persisted.fps == 60


def test_v283_obs_url_syntax_no_at_in_unicast():
    """Valida que build_client_urls genere URLs para OBS sin '@' en transmisiones UDP Unicast."""
    urls_remote = build_client_urls(
        host="192.168.1.50",
        port=9000,
        protocol="udp",
        udp_mode="unicast",
        udp_host="192.168.1.100",
    )
    assert urls_remote["obs_url"] == "udp://192.168.1.100:9000"
    assert "@" not in urls_remote["obs_url"]

    urls_local = build_client_urls(
        host="192.168.1.50",
        port=9000,
        protocol="udp",
        udp_mode="unicast",
        udp_host="127.0.0.1",
    )
    assert urls_local["obs_url"] == "udp://127.0.0.1:9000"
    assert "@" not in urls_local["obs_url"]


def test_v283_vlc_caching_300ms_and_clean_command():
    """Valida que VLC use búfer seguro de 300 ms sin directivas desestabilizadoras :clock-jitter=0 ni :clock-synchro=0."""
    urls = build_client_urls(
        host="192.168.1.50",
        port=9000,
        protocol="udp",
        udp_mode="unicast",
        udp_host="192.168.1.100",
    )
    assert urls["vlc_caching_ms"] == 300
    vlc_cmd = urls["vlc_command"]
    assert ":network-caching=300" in vlc_cmd
    assert ":drop-late-frames" in vlc_cmd
    assert ":skip-frames" in vlc_cmd

    # El comando renderizado en producción debe ser str limpio sin clock-jitter ni clock-synchro
    assert type(vlc_cmd) is str
    assert ":clock-jitter=0" not in vlc_cmd
    assert ":clock-synchro=0" not in vlc_cmd

    # Playlist XSPF por defecto a 300ms
    xspf = generate_vlc_xspf_playlist("udp://192.168.1.100:9000", "Camara 1")
    assert "network-caching=300" in xspf
    assert "clock-jitter=0" not in xspf
    assert "clock-synchro=0" not in xspf


@pytest.mark.asyncio
async def test_v283_ffmpeg_aspect_ratio_preservation_and_mjpeg_priority():
    """Valida prioridad MJPEG para 1080p y filtro de reescalado defensivo con preservación de aspect ratio."""
    # 1. Prioridad MJPEG en 1080p para webcams
    cfg_1080 = {
        "device_path": "Webcam HD Pro",
        "resolution": "1080p",
        "fps": 60,
        "zerolatency": True,
        "protocol": "udp",
        "udp_host": "192.168.1.100",
        "udp_mode": "unicast",
    }
    cmd_1080, _, _ = await build_ffmpeg_command(cfg_1080, force_cpu=True)
    assert "-vcodec" in cmd_1080
    vcodec_idx = cmd_1080.index("-vcodec")
    assert cmd_1080[vcodec_idx + 1] == "mjpeg"

    # Flags MPEG-TS para UDP Unicast
    assert "-muxdelay" in cmd_1080
    assert "-pat_period" in cmd_1080
    assert "-pcr_period" in cmd_1080
    assert "-flush_packets" in cmd_1080
    assert "-pes_payload_size" in cmd_1080

    # 2. Reescalado defensivo que preserva relación de aspecto (dshow_options_failed)
    cfg_failed = {
        "device_path": "Webcam Fallback",
        "resolution": "1080p",
        "fps": 60,
        "zerolatency": True,
        "dshow_options_failed": True,
        "protocol": "udp",
        "udp_host": "192.168.1.100",
        "udp_mode": "unicast",
    }
    cmd_failed, _, _ = await build_ffmpeg_command(cfg_failed, force_cpu=True)
    vf_idx = cmd_failed.index("-vf")
    vf_val = cmd_failed[vf_idx + 1]
    assert "force_original_aspect_ratio=decrease" in vf_val
    assert "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" in vf_val

    # 3. Soporte para protocolo RTP
    cfg_rtp = {
        "device_path": "Webcam RTP",
        "resolution": "720p",
        "fps": 60,
        "protocol": "rtp",
        "udp_host": "192.168.1.100",
        "port": 9002,
    }
    cmd_rtp, _, _ = await build_ffmpeg_command(cfg_rtp, force_cpu=True)
    assert "-payload_type" in cmd_rtp
    pt_idx = cmd_rtp.index("-payload_type")
    assert cmd_rtp[pt_idx + 1] == "96"
    assert cmd_rtp[pt_idx - 2] == "-f" and cmd_rtp[pt_idx - 1] == "rtp"


def test_v283_win32_pcore_affinity_detection():
    """Valida la detección de máscara de afinidad de P-Cores con Win32 API."""
    mask = get_pcore_affinity_mask()
    assert isinstance(mask, int)
    assert mask > 0

    # Probar que elevate_process_priority acepte core_mask
    elevate_result = elevate_process_priority(os.getpid(), core_mask=mask)
    assert isinstance(elevate_result, bool)


def test_v283_uvc_auto_exposure_graceful_handling():
    """Valida degradación elegante de UVC control para dispositivos virtuales, no existentes o no soportados."""
    # 1. Dispositivo virtual
    assert lock_uvc_auto_exposure("DispositivoVirtualInexistente_12345", max_shutter_sec=1 / 60.0) is False

    # 2. Dispositivo no existente sin palabra clave virtual
    assert lock_uvc_auto_exposure("CamaraFisicaInexistente_9999", max_shutter_sec=1 / 60.0) is False

    # 3. Dispositivo vacío o nulo
    assert lock_uvc_auto_exposure("", max_shutter_sec=1 / 60.0) is False

    # 4. Capacidades UVC estructuradas
    from core.uvc_control import get_uvc_camera_capabilities

    caps = get_uvc_camera_capabilities("Camara_Test")
    assert isinstance(caps, dict)
    assert caps["target_max_shutter"] == "1/60s"


def test_v283_mediamtx_lazy_lifecycle():
    """Valida el ciclo de vida lazy de MediaMTX (arranque bajo demanda y apagado por inactividad)."""
    assert hasattr(mediamtx_manager, "ensure_started")
    assert hasattr(mediamtx_manager, "register_srt_stream")
    assert hasattr(mediamtx_manager, "unregister_srt_stream")
    assert hasattr(mediamtx_manager, "register_webrtc_activity")


def test_v283_rtp_sdp_generation():
    """Valida la generación de archivos de sesión SDP para transmisión RTP en OBS Studio."""
    sdp = generate_rtp_sdp(host="192.168.1.100", port=9000)
    assert "v=0" in sdp
    assert "m=video 9000 RTP/AVP 96" in sdp
    assert "c=IN IP4 192.168.1.100" in sdp
    assert "a=rtpmap:96 H264/90000" in sdp


def test_v283_ui_i18n_honest_latency_claims():
    """Valida que se hayan purgado las falsas promesas de latencia comercial en i18n e index.html."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    i18n_path = os.path.join(repo_root, "gui", "static", "i18n.js")
    with open(i18n_path, "r", encoding="utf-8") as f:
        i18n_content = f.read()

    assert "<100ms real sin buffers" not in i18n_content
    assert "Modo Zerolatency (VBV 1.5 frames, B-frames=0, latencia mínima)" in i18n_content
    assert "UDP Unicast LAN (Hacia otra PC o OBS — Recomendado)" in i18n_content
    assert ":network-caching=300" in i18n_content

    html_path = os.path.join(repo_root, "gui", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    assert "BÚFER SEGURO VLC" in html_content
    assert "300 ms" in html_content
    assert "<100ms real sin buffers" not in html_content
