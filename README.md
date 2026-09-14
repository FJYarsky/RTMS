# RTMS — Real-Time Multicam System v2.0.3

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?logo=windows)](https://microsoft.com)
[![Protocol](https://img.shields.io/badge/Streaming-SRT%20%7C%20UDP%20Multicast-teal)](https://www.srtalliance.org/)
[![Security](https://img.shields.io/badge/Security-Local%20Token%20Auth-green.svg)](#-seguridad-y-hardening)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Joaqu%C3%ADn%20Yarsky-orange)](mailto:joaquinyarsky@gmail.com)

**RTMS (Real-Time Multicam System)** es una estación servidora de video multicámara de ultra baja latencia para Windows, concebida para entornos exigentes de producción en vivo y streaming profesional (OBS Studio, vMix, VLC).

Permite conectar múltiples cámaras mediante **DirectShow** (webcams USB, capturadoras HDMI/SDI, cámaras PTZ) a una PC servidora y retransmitir cada señal a través de la red local (LAN) usando **SRT (Secure Reliable Transport)** con latencia sub-80ms y corrección automática de paquetes perdidos, o **UDP Multicast**.

---

## 🔒 Seguridad y Hardening (v2.0.3)

* **CORS Restringido**: Eliminado el comodín `allow_origins=["*"]`. El backend ahora solo acepta peticiones desde su propio origen local dinámico (`127.0.0.1:<puerto>`), blindando el equipo contra ataques de tipo *Localhost CSRF / Drive-by* desde navegadores web.
* **Autenticación por Token de Sesión (`X-RTMS-Token`)**: La aplicación genera un token criptográfico seguro al arrancar que es validado en todas las peticiones que modifican el sistema (`POST /api/*`).
* **Enmascaramiento de Contraseñas SRT**: La API oculta las contraseñas reales (`••••••••`), evitando fugas de credenciales en la red o logs.
* **Passphrases Seguras por Defecto**: Las nuevas cámaras creadas con protocolo SRT generan automáticamente contraseñas de 12 caracteres para que los enlaces nunca queden expuestos.
* **Rotación de Logs (`RotatingFileHandler`)**: Control estricto del archivo `rtms.log` (5 MB, 3 copias) para evitar consumo excesivo de disco en operación desatendida 24/7.
* **Endpoint de Salud (`/healthz`)**: Verificación de estado ligera para supervisores de procesos del sistema operativo.

---

## 🚀 Características Principales

* **SRT Listener de Ultra Baja Latencia (`zerolatency`)**:
  * Latencia real inferior a 80 ms (*Glass-to-Glass*).
  * Eliminación de los 700 ms de búfer interno de MPEG-TS mediante `-muxdelay 0 -muxpreload 0 -flush_packets 1`.
  * Descarte proactivo de paquetes demorados con `tlpktdrop=1`.
* **Aceleración por GPU Universal (`-pix_fmt yuv420p`)**:
  * Compatibilidad total con NVIDIA NVENC, AMD AMF e Intel QuickSync sin fallos de formato de color.
  * **Fallback Automático a CPU (`libx264`)** en caliente si la GPU se sobrecarga o el driver falla.
* **Operación Desatendida (*Unattended Mode*)**:
  * Autoarranque de cámaras memorizadas al encender la PC sin requerir operador humano.
  * Resiliencia ante retrasos en la inicialización USB/PnP de Windows con sondeo periódico continuo.
  * Watchdog inteligente con **reseteo de errores tras estabilidad** y **backoff exponencial** (5s a 60s).
* **Bloqueo de Instancia Única (*Single Instance Lock*)**:
  * Mutex nativo de Windows que impide abrir el software dos veces por error.
* **Minimización a la Bandeja del Sistema (*System Tray*)**:
  * Icono interactivo en la barra de tareas de Windows.
* **Telemetría en Vivo (HUD)**:
  * Monitoreo en tiempo real de CPU %, RAM %, y lectura directa de FPS y Bitrate emitido por cada cámara.
* **Parada de Emergencia y Cierre Seguro (*Graceful Teardown*)**:
  * Cierre limpio con señal `q` a FFmpeg para evitar congelamientos en OBS Studio al detener flujos.

---

## 🏛️ Arquitectura del Repositorio

```
RTMS/
├── api/                   # Capa REST API (FastAPI) con autenticación CSRF
│   ├── routes.py          # Endpoints de control, telemetría y configuración
│   └── schemas.py         # Modelos de datos Pydantic
├── core/                  # Procesamiento multimedia y sistema
│   ├── ffmpeg_mgr.py      # Motor FFmpeg con watchdog resiliente y telemetría
│   ├── hardware.py        # Sondeo de dispositivos DirectShow
│   ├── config_mgr.py      # Gestor de persistencia seguro
│   ├── system_env.py      # Optimizaciones de energía y firewall sin consolas CMD
│   ├── autostart.py       # Gestor de autoarranque silencioso
│   ├── single_instance.py # Mutex Win32 para instancia única
│   └── tray_icon.py       # Integración con System Tray (pystray)
├── gui/                   # Interfaz de usuario SPA
│   ├── static/            # CSS y JavaScript seguro con token X-RTMS-Token
│   └── templates/         # Plantilla index.html con inyección de token
├── config/                # Plantillas de configuración
│   └── config.example.json # Plantilla limpia para nuevos despliegues
├── scripts/               # Scripts de utilidad
│   └── setup_binaries.ps1 # Descarga automática de FFmpeg oficial
├── tests/                 # Suite de pruebas automatizadas (pytest)
│   ├── test_hardware_parser.py
│   ├── test_config_mgr.py
│   └── test_security.py
├── main.py                # Punto de entrada principal
├── run.bat                # Lanzador silencioso (pythonw.exe)
├── run_silent.vbs         # Lanzador 100% invisible para Windows
├── build_portable.bat     # Generador de ejecutable portable
├── requirements.txt       # Dependencias de producción y test fijadas
├── CHANGELOG.md           # Historial de cambios
├── SECURITY.md            # Política de seguridad
└── CONTRIBUTING.md        # Guía para colaboradores
```

---

## 📦 Puesta en Marcha

### 1. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configuración de FFmpeg
RTMS requiere un binario de **FFmpeg** con soporte DirectShow, NVENC y SRT en `bin/ffmpeg.exe`. Puedes descargarlo e instalarlo automáticamente ejecutando en PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_binaries.ps1
```

### 3. Ejecución
* Modo normal sin consola visible: Haz doble clic en `run.bat`.
* Modo 100% invisible: Haz doble clic en `run_silent.vbs`.

### 4. Ejecución de Tests
```bash
pytest tests/ -v
```

---

## 📺 Guía de Conexión en OBS Studio

1. Abre **OBS Studio** en la computadora receptora.
2. En el panel de **Fuentes**, haz clic en `+` y selecciona **Fuente multimedia**.
3. **Desmarca** la casilla `Archivo local`.
4. En **Entrada**, pega la URL generada:
   ```text
   srt://192.168.1.X:9000?mode=caller&latency=120000
   ```
   *(Si configuraste contraseña, agrega `&passphrase=TU_CONTRASEÑA` al final de la URL)*.
5. En **Formato de entrada**, escribe:
   ```text
   mpegts
   ```
6. Haz clic en **Aceptar**. La señal comenzará a emitirse en tiempo real.

---

## 👤 Autor y Soporte Oficial

**Joaquín Yarsky**
* **Correo Electrónico**: [joaquinyarsky@gmail.com](mailto:joaquinyarsky@gmail.com)
* **Teléfono / Celular**: [+54 2625-437980](tel:+542625437980)
* **WhatsApp Directo**: [https://wa.me/5492625437980](https://wa.me/5492625437980)

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
