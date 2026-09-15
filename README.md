# RTMS — Real-Time Multicam System v2.1.0

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?logo=windows)](https://microsoft.com)
[![Protocol](https://img.shields.io/badge/Streaming-SRT%20%7C%20UDP%20Multicast-teal)](https://www.srtalliance.org/)
[![Security](https://img.shields.io/badge/Security-Strict%20Zero--Secret%20Logs-green.svg)](#-seguridad-y-hardening)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Joaqu%C3%ADn%20Yarsky-orange)](mailto:joaquinyarsky@gmail.com)

**RTMS (Real-Time Multicam System)** es una estación servidora de video multicámara de ultra baja latencia para Windows, concebida para entornos exigentes de producción en vivo y streaming profesional (OBS Studio, vMix, VLC).

Permite conectar múltiples cámaras mediante **DirectShow** (webcams USB, capturadoras HDMI/SDI, cámaras PTZ) a una PC servidora y retransmitir cada señal a través de la red local (LAN) usando **SRT (Secure Reliable Transport)** con latencia ultra-baja (diseñado para rendimiento sub-100ms en condiciones óptimas de hardware y red cableada con corrección automática de pérdidas de paquetes) o **UDP Multicast**.

---

## 🔒 Seguridad y Hardening (v2.1.0)

* **Vista Previa On-Demand Desacoplada**: Monitorización de video en vivo (MJPEG web y FFplay nativo) totalmente independiente del pipeline de emisión principal, garantizando 0.00% de uso de CPU/GPU en reposo y sin riesgo de bloqueo por buffers de lectura lenta.
* **Cero Secretos en Logs y Memoria**: Implementación de un módulo de sanitización centralizado (`core/sanitizer.py`) que enmascara automáticamente contraseñas SRT y tokens en comandos FFmpeg, buffers de memoria y archivos de registro en disco.
* **Autenticación Estricta de API (`X-RTMS-Token`)**: Todos los endpoints mutantes (`POST`) y los endpoints de inspección sensibles (`GET /api/status`, `/api/stream/logs`, `/api/system/metrics`, `/api/power/status`) exigen el token criptográfico de sesión local. Únicamente `/healthz` permanece público para supervisores externos.
* **CORS Restringido**: Enlace determinista y exclusivo al origen local dinámico (`127.0.0.1:<puerto>`), previniendo ataques de tipo *Localhost CSRF / Drive-by* desde navegadores externos.
* **Protección Criptográfica en Disco (Windows DPAPI)**: Frases de paso SRT cifradas en reposo mediante Windows DPAPI (`core/secrets_mgr.py`), atadas de forma nativa a la cuenta del usuario, con deduplicación lógica en memoria para detener escrituras redundantes a disco.
* **Prevención Activa de Suspensión**: Modo activo de ejecución (`SetThreadExecutionState`) que impide la suspensión de Windows en laptops y portátiles durante transmisiones en directo.
* **Rotación de Logs (`RotatingFileHandler`)**: Control estricto de tamaño para `rtms.log` (5 MB, 3 copias de respaldo) para estabilidad desatendida 24/7.
* **Empaquetado Seguro sin Fuga de Credenciales**: Generación portable que excluye `config.json` y distribuye únicamente la plantilla de ejemplo `config.example.json` junto con `THIRD_PARTY_NOTICES.md`.

---

## 🚀 Características Principales

* **Vista Previa de Video On-Demand y Modo Encuadre**:
  * Visualización en tiempo real vía MJPEG Streaming en la UI web y ventana externa con FFplay.
  * Captura de cuadro estático para encuadre DirectShow cuando la cámara está detenida.
  * Consumo nulo de recursos (0.00% CPU/GPU) fuera de uso.
* **Optimización Térmica y Clasificación Inteligente de Cámaras**:
  * Aislamiento de cámaras virtuales de IA (`NVIDIA Broadcast`, etc.) con auto-arranque desactivado para proteger el presupuesto térmico de GPUs dedicadas (e.g. RTX 4050).
  * Detección única con caché global de codificadores (`NVENC`, `QuickSync`, `AMF`, `libx264`).
* **SRT Listener de Ultra Baja Latencia con Modo `zerolatency` Funcional**:
  * Diseñado para latencia sub-100ms *Glass-to-Glass* con conmutación real de parámetros (`tlpktdrop=1`, `-muxdelay 0 -muxpreload 0 -flush_packets 1`, `-tune zerolatency`).
  * Perfil alternativo balanceado para broadcast con tolerancia a fluctuaciones de red.
* **Aceleración Universal por GPU y Fallback Seguro**:
  * Compatibilidad nativa con NVIDIA NVENC, Intel QuickSync y AMD AMF (`-pix_fmt yuv420p`).
  * **Fallback transparente y libre de carreras a CPU (`libx264`)**: Bloqueo de exclusión mutua (`asyncio.Lock`) por cámara y parada limpia antes de conmutar de encoder.
  * Granularidad por stream: la degradación temporal de una GPU no afecta a las demás cámaras.
* **Persistencia Atómica y Resiliente (`core/config_mgr.py`)**:
  * Escritura atómica (`.tmp` $\rightarrow$ `fsync` $\rightarrow$ `replace`), copias de respaldo continuas (`.bak`) y framework de migraciones de versión de esquema.
  * Identidad determinista de cámara (`camera_id` UUID) desacoplada de la ruta física del bus USB.
* **Gestor Inteligente de Puertos (`PortManager`)**:
  * Verificación activa de sockets ocupados antes de asignación (rango 9000–9200) y reciclaje de puertos liberados.
* **Watchdog No Bloqueante con Detección de Desconexión Física**:
  * Reintentos con backoff exponencial independiente (5s a 60s) sin congelar la supervisión de los demás flujos.
  * Transición a `DISCONNECTED` ante desconexión física de cables USB y relanzamiento automático al reconectar.
* **Herramienta de Diagnóstico CLI (`RTMS Doctor`)**:
  * Comando interactivo para validar OS, FFmpeg, soporte SRT, encoders GPU, puertos y cámaras (`python -m core.doctor` o `python core/doctor.py`).
* **Copia de Seguridad y Migración de Configuración en UI**:
  * Exportación e importación de la configuración completa en formato JSON desde el panel web.

---

## 🏛️ Arquitectura del Repositorio

```
RTMS/
├── api/                   # Capa REST API (FastAPI) protegida por X-RTMS-Token
│   ├── routes.py          # Endpoints de control, telemetría, vistas previas y configuración
│   └── schemas.py         # Modelos de datos Pydantic estrictos
├── core/                  # Lógica del motor y resiliencia de sistema
│   ├── __version__.py     # Fuente única y centralizada de versión (v2.1.0)
│   ├── sanitizer.py       # Sanitización estricta de contraseñas y secretos
│   ├── secrets_mgr.py     # Cifrado nativo de contraseñas con Windows DPAPI
│   ├── port_mgr.py        # Gestor de puertos sin colisiones de red
│   ├── config_mgr.py      # Persistencia atómica, backups .bak y migraciones
│   ├── ffmpeg_mgr.py      # Motor FFmpeg, teardown limpio y watchdog no bloqueante
│   ├── preview_mgr.py     # Gestor de vista previa on-demand (MJPEG y FFplay)
│   ├── hardware.py        # Sondeo DirectShow y caché de capacidades GPU
│   ├── system_env.py      # Optimizaciones de energía Windows, stay-awake y firewall
│   ├── autostart.py       # Gestor de autoarranque silencioso
│   ├── doctor.py          # Herramienta de diagnóstico CLI (RTMS Doctor)
│   ├── single_instance.py # Mutex Win32 para instancia única
│   └── tray_icon.py       # Integración con System Tray (pystray)
├── gui/                   # Interfaz de usuario SPA
│   ├── static/            # CSS y JavaScript seguro (apiFetch y safe DOM)
│   └── templates/         # Plantilla index.html con inyección de token
├── docs/                  # Documentación técnica avanzada
│   ├── HARDWARE.md        # Matriz de compatibilidad de GPUs y encoders
│   └── TROUBLESHOOTING.md # Guía paso a paso de resolución de problemas
├── scripts/               # Scripts de instalación y soporte
│   └── setup_binaries.ps1 # Descarga segura de FFmpeg con verificación SHA256
├── tests/                 # Suite de 35 pruebas automatizadas (pytest)
│   ├── test_sanitizer.py
│   ├── test_command_builder.py
│   ├── test_config_persistence.py
│   ├── test_config_isolation.py
│   ├── test_port_mgr.py
│   ├── test_preview.py
│   ├── test_stream_lifecycle.py
│   ├── test_security.py
│   ├── test_config_mgr.py
│   └── test_hardware_parser.py
├── pyproject.toml         # Configuración del proyecto, ruff y pytest
├── requirements.txt       # Dependencias exclusivas de producción
├── requirements-dev.txt   # Dependencias de desarrollo, testing y linting
├── run.bat                # Lanzador silencioso (pythonw.exe)
├── run_silent.vbs         # Lanzador 100% invisible para Windows
├── build_portable.bat     # Generador de ejecutable portable
├── CHANGELOG.md           # Historial cronológico de cambios
├── SECURITY.md            # Política de divulgación de vulnerabilidades
├── CONTRIBUTING.md        # Guía para colaboradores
├── THIRD_PARTY_NOTICES.md # Licencias de componentes de terceros (FFmpeg/GPL)
└── conftest.py            # Fixtures de pytest y aislamiento de entorno
```

---

## 📦 Puesta en Marcha

### 1. Instalación de Dependencias
```bash
pip install -r requirements.txt
# Para desarrollo y pruebas:
pip install -r requirements-dev.txt
```

### 2. Configuración de FFmpeg
Ejecuta el script de PowerShell para descargar y verificar mediante SHA256 la versión oficial de FFmpeg:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_binaries.ps1
```

### 3. Diagnóstico de Salud del Sistema (RTMS Doctor)
```bash
python core/doctor.py
```

### 4. Ejecución de Pruebas
```bash
pytest tests/ -v
```
