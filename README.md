# RTMS — Real-Time Multicam System

<div align="center">

[![Platform](https://img.shields.io/badge/Plataforma-Windows%2010%20%7C%2011-0078D4?logo=windows&logoColor=white)](https://microsoft.com)
[![Protocol](https://img.shields.io/badge/Streaming-SRT%20%7C%20UDP-0d9488)](https://www.srtalliance.org/)
[![Security](https://img.shields.io/badge/Seguridad-DPAPI%20%7C%20Token-10b981)](#-seguridad)
[![CI](https://github.com/FJYarsky/RTMS/actions/workflows/ci.yml/badge.svg)](https://github.com/FJYarsky/RTMS/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Pruebas-113%20Aprobadas-10b981)](tests/)
[![License](https://img.shields.io/badge/Licencia-MIT-gray.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Autor-Joaqu%C3%ADn%20Yarsky-f59e0b)](mailto:joaquinyarsky@gmail.com)

**Servidor de video multicámara de baja latencia para Windows vía SRT y UDP.**

[Inicio Rápido](#-inicio-rápido) • [Configuración OBS](#-configuración-en-obs-studio) • [Características](#-características) • [Seguridad](#-seguridad) • [Estructura](#-estructura-del-proyecto) • [Contacto](#-contacto-y-soporte)

---

</div>

## 📌 Descripción

**RTMS (Real-Time Multicam System)** es una estación de streaming para Windows que captura dispositivos DirectShow (cámaras web, capturadoras HDMI y cámaras virtuales) y los transmite de forma individual por red local mediante **SRT** o **UDP Multicast** hacia OBS Studio, vMix o VLC con latencia mínima (<100ms) y telemetría en tiempo real.

---

## ⚡ Inicio Rápido

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/FJYarsky/RTMS.git
cd RTMS
pip install -r requirements.txt

# 2. Descargar binarios de FFmpeg (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/setup_binaries.ps1

# 3. Iniciar la aplicación
python main.py
```

> [!TIP]
> En producción, ejecuta `run.bat` o `run_silent.vbs` para iniciar en segundo plano sin consola visible.

---

## 📺 Configuración en OBS Studio

1. Agrega una **Fuente multimedia** (`Media Source`) en OBS.
2. **Desmarca** la opción `Archivo local`.
3. En **Entrada** (`Input`), ingresa la URL de la cámara:
   ```text
   srt://192.168.1.X:9000?mode=caller&latency=120000
   ```
   *(Si configuraste contraseña, añade `&passphrase=TU_CLAVE`)*.
4. En **Formato de entrada** (`Input Format`), escribe:
   ```text
   mpegts
   ```
5. Haz clic en **Aceptar** para iniciar la recepción del flujo.

---

## 🚀 Características

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
├── docs/                  # Guías de compatibilidad de hardware y troubleshooting
├── scripts/               # Scripts de descarga y verificación de FFmpeg
├── tests/                 # Suite de pruebas automatizadas (113 tests)
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
 
