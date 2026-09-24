# RTMS — Real-Time Multicam System

<div align="center">

[![Website](https://img.shields.io/badge/Sitio%20Web-fjyarsky.github.io%2FRTMS-0ea5e9?logo=googlechrome&logoColor=white)](https://fjyarsky.github.io/RTMS/)
[![Platform](https://img.shields.io/badge/Plataforma-Windows%2010%20%7C%2011-0078D4?logo=windows&logoColor=white)](https://microsoft.com)
[![Protocol](https://img.shields.io/badge/Streaming-SRT%20%7C%20WebRTC%20%7C%20UDP-0d9488)](https://www.srtalliance.org/)
[![Security](https://img.shields.io/badge/Seguridad-DPAPI%20%7C%20Token-10b981)](#-seguridad)
[![Snyk](https://img.shields.io/badge/Snyk-Monitoreo%20Continuo-4c1?logo=snyk&logoColor=white)](SECURITY.md)
[![CI](https://github.com/FJYarsky/RTMS/actions/workflows/ci.yml/badge.svg)](https://github.com/FJYarsky/RTMS/actions/workflows/ci.yml)
[![Discussions](https://img.shields.io/badge/Discussions-Comunidad-7c3aed?logo=github&logoColor=white)](https://github.com/FJYarsky/RTMS/discussions)
[![License](https://img.shields.io/badge/Licencia-MIT-gray.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Autor-Joaqu%C3%ADn%20Yarsky-f59e0b)](mailto:joaquinyarsky@gmail.com)

**Servidor de video multicámara de baja latencia para Windows con ingesta desacoplada vía MediaMTX, SRT y UDP.**

[Sitio Web Oficial](https://fjyarsky.github.io/RTMS/) • [Inicio Rápido](#-inicio-rápido) • [Configuración OBS](#-configuración-en-obs-studio) • [Características](#-características) • [Seguridad](#-seguridad) • [Discusiones](https://github.com/FJYarsky/RTMS/discussions) • [Contacto](#-contacto-y-soporte)

---

</div>

## 📌 Descripción

**RTMS (Real-Time Multicam System)** es una estación de streaming para Windows que captura dispositivos DirectShow (cámaras web, capturadoras HDMI y cámaras virtuales) y centraliza su transmisión de ultra baja latencia (<100ms) mediante **MediaMTX** y **SRT** / **UDP Multicast** hacia OBS Studio, vMix o VLC con telemetría en tiempo real, persistencia transaccional ACID en SQLite WAL y blindaje de procesos por Kernel (Win32 Job Objects).

> [!TIP]
> 🌐 **Sitio Web Oficial & Descarga Directa**: Visita **[fjyarsky.github.io/RTMS](https://fjyarsky.github.io/RTMS/)** para descargar el ejecutable portable oficial (`rtms.exe`), consultar la matriz de compatibilidad de hardware y acceder a guías de configuración.

---

## ⚡ Inicio Rápido

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/FJYarsky/RTMS.git
cd RTMS
pip install -r requirements.txt

# 2. Descargar binarios de FFmpeg y MediaMTX (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/setup_binaries.ps1

# 3. Iniciar la aplicación
python main.py
```

> [!TIP]
> En producción, ejecuta directamente el archivo ejecutable portable `rtms.exe` (o `run.bat` al ejecutar desde código fuente en modo desarrollo).

---

## 📺 Configuración en OBS Studio

1. Agrega una **Fuente multimedia** (`Media Source`) en OBS.
2. **Desmarca** la opción `Archivo local`.
3. En **Entrada** (`Input`), ingresa la URL de la cámara (multiplexada en el puerto central MediaMTX):
   ```text
   srt://192.168.1.X:8890/?streamid=read:CAM_ID
   ```
   *(Copia la dirección directamente con un clic desde el botón "Copiar URL" en RTMS)*.
4. En **Formato de entrada** (`Input Format`), escribe:
   ```text
   mpegts
   ```
5. Haz clic en **Aceptar** para iniciar la recepción del flujo.

---

## 🚀 Características

- **Ingesta Desacoplada (MediaMTX)**: Ingesta continua en localhost. Las desconexiones de OBS o vMix no reinician FFmpeg ni provocan parpadeos en las cámaras físicas.
- **Blindaje a Nivel Kernel**: Subprocesos asignados a un Win32 Job Object con `KILL_ON_JOB_CLOSE`. Cero procesos huérfanos.
- **Persistencia ACID (SQLite WAL)**: Base de datos transaccional con Write-Ahead Logging y migración automática y transparente desde configuraciones previas.
- **Papelera de Restauración de Cámaras**: Recuperación instantánea con un clic de cámaras eliminadas u ocultadas sin requerir reseteos de fábrica.
- **Telemetría en Vivo**: Monitor de CPU, GPU (NVML nativo <1ms), RAM, tráfico de red y bitrate.
- **Ultra Baja Latencia**: Modo `zerolatency` sobre SRT con recuperación ante pérdida de paquetes.
- **Aceleración por GPU**: Compatible con NVIDIA NVENC, Intel QSV y AMD AMF, con fallback automático a CPU (`libx264`).
- **Vista Previa On-Demand**: Streaming MJPEG en el navegador y visor nativo FFplay con consumo cero en reposo.
- **Reconexión Automática (PnP)**: Detección de desconexión física de cámaras USB y relanzamiento al reconectar.
- **Aislamiento de Cámaras Virtuales**: Detección inteligente de software (ej. NVIDIA Broadcast) para preservar GPU.
- **Prevención de Suspensión**: Mantiene activos los puertos USB y la máquina durante transmisiones en vivo.

---

## 🔒 Seguridad

| Mecanismo | Descripción |
| :--- | :--- |
| **Sanitización de Logs y URLs** | Oculta automáticamente contraseñas SRT y tokens en consola, registros y memoria. |
| **Cifrado DPAPI** | Contraseñas protegidas mediante las API criptográficas del usuario de Windows sin fuga en caso de fallo. |
| **Tickets Efímeros (MJPEG)** | Tokens temporales criptográficos de un solo uso para previsualizaciones sin exponer credenciales globales. |
| **Cabeceras HTTP y Air-Gapped** | UI 100% offline sin dependencias CDN y cabeceras estrictas (CSP, X-Frame-Options, nosniff). |
| **Token de Sesión** | Endpoints de control y telemetría autenticados con cabecera `X-RTMS-Token`. |
| **CORS Localhost** | Restricción estricta de origen a `127.0.0.1` para mitigar accesos indebidos desde la red. |

---

## 🏛️ Estructura del Proyecto

```text
RTMS/
├── api/                   # API REST FastAPI y esquemas de validación Pydantic
├── core/                  # Motor de streaming, hardware DirectShow y telemetría
├── gui/                   # Panel de control web (SPA, plantillas y estilos)
├── docs/                  # Guías de hardware, troubleshooting y branding oficial (BRANDING.md)
├── scripts/               # Scripts de descarga y verificación de FFmpeg
├── tests/                 # Suite de pruebas automatizadas (186 tests)
├── config/                # Plantilla de configuración (config.example.json)
├── main.py                # Punto de entrada de la aplicación
├── run.bat                # Lanzador rápido para Windows
├── pyproject.toml         # Configuración del paquete y dependencias
└── README.md              # Documentación principal
```

---

## 🧪 Pruebas Automatizadas

```bash
# Ejecutar suite completa (113 tests):
pytest tests/ -v

# Verificación de estilo con Ruff:
ruff check .
```

---

## 👨‍💻 Contacto y Soporte

Desarrollado y mantenido por **Joaquín Yarsky**:
* 📧 Email: [joaquinyarsky@gmail.com](mailto:joaquinyarsky@gmail.com)
* 🌐 Repositorio: [github.com/FJYarsky/RTMS](https://github.com/FJYarsky/RTMS)

---

## 📄 Licencia

Distribuido bajo licencia **MIT**. Ver archivo [LICENSE](LICENSE). Licencias de terceros detalladas en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
