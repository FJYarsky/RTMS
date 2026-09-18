# Notas Oficiales de Lanzamiento — RTMS (Real-Time Multicam System)

Historial completo y notas oficiales de lanzamiento organizadas cronológicamente para cada versión de RTMS.

---

## RTMS v2.2.6 — Corrección Crítica de Conexión SRT, Optimización UDP 1080p60 y Suite de Diagnóstico FFmpeg
*(2026-09-17)*

### 🛠️ Corrección Crítica de Entablado de Conexión SRT y Copia de URL
- **Resolución de Rechazo por Contraseña Faltante (`ERROR:UNSECURE`)**:
  - RTMS genera passphrases criptográficas seguras al registrar cámaras, pero la interfaz web copiaba la URL `srt://IP:port?mode=caller...` omitiendo el parámetro `&passphrase=...`. Sockets externos como OBS Studio o vMix eran rechazados inmediatamente con `ERROR:UNSECURE (Password required or unexpected)`.
  - Se implementó el endpoint protegido `GET /api/stream/{device_path}/connect_url` en `api/routes.py` que calcula y devuelve la URL completa y funcional con su passphrase configurada y codificación URL segura.
  - Se actualizó `gui/static/app.js` (`copyUrlByIndex`) para consultar este endpoint al pulsar "Copiar URL", copiando al portapapeles la dirección exacta y garantizando la conexión al 100%.
- **Resiliencia del Listener SRT ante Desconexiones de Clientes**:
  - En `core/ffmpeg_mgr.py`, el Watchdog detecta cuando FFmpeg finaliza tras la desconexión normal de un cliente receptor (`-5 I/O error`) y reinicia el proceso listener de inmediato con penalización cero y sin retardos de *backoff*, dejando el socket disponible para reconexión instantánea.

### 🚀 Optimización y Estabilidad Continua de Streaming UDP a 1080p @ 60 FPS
- **Ampliación de Buffer de Socket de Red a 4 MB**:
  - El buffer de socket UDP en `core/ffmpeg_mgr.py` (`build_multicast_url`) se incrementó de 64 KB (`buffer_size=65535`) a 4 MB (`buffer_size=4194304&overrun_nonfatal=1&fifo_size=50000000`). Esto elimina la saturación de socket en Windows a altas tasas de bits (6–12 Mbps) y erradica por completo la pérdida de paquetes y tirones de framerate.
- **Inyección Forzada de Cabeceras SPS/PPS (`repeat-headers` y `dump_extra`)**:
  - Se añadieron los parámetros `-x264-params repeat-headers=1` (para CPU `libx264`) y `-forced-idr 1` (para GPU `h264_nvenc`), combinados con el bitstream filter `-bsf:v dump_extra` para MPEG-TS. Receptores que conectan con la transmisión ya iniciada reciben de inmediato los parámetros de secuencia sin arrojar errores `non-existing PPS 0 referenced`.
- **Soporte Nativo de Fuentes de Cámara Virtual (`virtual://` / `testsrc`)**:
  - `core/ffmpeg_mgr.py` ahora admite cámaras virtuales `virtual://` que generan patrones sintéticos `testsrc2` en tiempo real, permitiendo transmitir y verificar 1080p60 continuo en hardware de test o sin cámara física 60fps.

### 🔬 Suite Integral de Diagnóstico, Digestión de Video y Pruebas en Vivo
- **Motor de Análisis y Digestión en Tiempo Real (`core/ffmpeg_tester.py`)**:
  - `VideoReceiverDigest`: Receptor y analizador de flujos en vivo que decodifica flujos SRT y UDP con `-progress pipe:1`, calculando FPS decodificados reales, bitrate instantáneo, estabilidad de jitter, frames descartados y errores de bitstream H.264.
  - `VirtualCameraSource`: Generador de video sintético calibrado con patrones `testsrc2`, barras SMPTE y reloj OSD con microsegundos a cualquier resolución y framerate.
  - `FFmpegDiagnosticSuite`: Orquestador de pruebas locales que valida binarios, códecs de hardware (NVENC/x264), dispositivos DirectShow y entablado de conexiones en bucle local (loopback).
- **Herramienta CLI de Consola (`scripts/test_ffmpeg_pipeline.py`)**:
  - CLI interactivo y automatizado con soporte nativo UTF-8 en consolas Windows, banderas de diagnóstico (`--all`, `--srt`, `--udp`, `--bench`, `--camera`, `--virtual-cam`).
- **Tests Automatizados de Integración (`tests/test_ffmpeg_live.py`)**:
  - 5 tests de integración en vivo añadidos a la suite oficial de Pytest, elevando la cobertura a 110 tests unitarios y de integración pasando al 100%.

---

## RTMS v2.2.5 — Desbloqueo Mark-of-the-Web, Ventana Nativa WebView2 y System Tray de Cero Latencia
*(2026-09-16)*

### 🚀 Desbloqueo Automático Mark-of-the-Web y Ejecución Nativa Garantizada
- **Eliminación Automática de Flujos NTFS Zone.Identifier (`unblock_app_binaries`)**:
  - En Windows, descargar archivos zip de releases desde la web adjunta automáticamente la marca de seguridad `Zone.Identifier` (`ZoneId=3`). Esto causaba que la capa de interoperabilidad unmanaged de .NET Framework bloqueara `Python.Runtime.dll` arrojando `Failed to resolve Python.Runtime.Loader.Initialize` y obligando a la aplicación a abrirse en Google Chrome.
  - Se implementó el desmarque nativo Win32 en `core/system_env.py` que recorre y desbloquea en milisegundos todos los binarios y bibliotecas de la aplicación al arrancar.
- **Configuración de Runtime CLR (`rtms.exe.config`)**:
  - Se añade el manifiesto de configuración `rtms.exe.config` autorizando explícitamente la carga de ensamblados remotos (`<loadFromRemoteSources enabled="true"/>`) y vinculando el runtime .NET 4.6.2+.
- **Empaquetado Completo de `clr_loader`**:
  - En `build_portable.bat`, se añade `--collect-all=clr_loader` y los módulos ffi nativos para empaquetar `ClrLoader.dll` junto a `rtms.exe`.

### ⚡ System Tray con Despacho Asíncrono y Cero Latencia
- **Desacoplamiento Total de la Bomba de Mensajes Win32**:
  - Todas las acciones del menú contextual en `core/tray_icon.py` (`Mostrar RTMS`, `Detener todas las transmisiones`, `Finalizar todos los procesos`, `Acerca de RTMS`, `Salir de RTMS`) ahora se ejecutan de forma estrictamente asíncrona en hilos de trabajo independientes (`daemon=True`).
  - La bomba de mensajes Win32 de `pystray` nunca se bloquea, garantizando que el menú contextual se despliegue instantáneamente (<1 ms) y siempre en la posición exacta del cursor.
- **Control de Sincronización de Ventana (`_main_window_ready`)**:
  - Se implementa una bandera de inicialización en `main.py` para sincronizar el estado del motor gráfico antes de interactuar con la ventana nativa.
  - Se erradican los retardos y congelamientos de 10 a 20 segundos (`events.shown.wait(10)`) que ocurrían al restaurar o consultar el modal Acerca de en estados transitorios o tras errores gráficos.

---

## RTMS v2.2.4 — Ventana Nativa WebView2, System Tray Avanzado y Limpieza Total de Procesos
*(2026-09-16)*

### 🖥️ Interfaz de Escritorio Nativa y Empaquetado Portable (WebView2)
- **Corrección Crítica de Ventana Nativa en Release Portable**:
  - En la distribución portable generada por PyInstaller, se empaquetan las dependencias nativas de `pythonnet` y se copian automáticamente todas las DLLs de WebView2 (`Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll` y la carpeta de arquitecturas `runtimes/`) junto a `icon.ico` hacia la raíz y `_internal` de `dist/rtms/`.
  - Se elimina definitivamente el fallo silencioso que forzaba a la aplicación a abrirse en el navegador por defecto (Google Chrome) en lugar del entorno de escritorio nativo con aceleración Edge WebView2.
- **Corrección de Diseño y Disposición Horizontal del HUD**:
  - Solucionada la alineación flexible de los indicadores de telemetría (CPU, GPU, RAM, Red, Bitrate) en el encabezado, eliminando el desbordamiento vertical tras la integración del nuevo botón de detención y salida.
- **Eliminación de Ventanas Duplicadas y Pestañas Periódicas**:
  - `show_window_from_tray()` en `main.py` valida la existencia de la ventana nativa (`_main_window`) e invoca exclusivamente `show()` y `restore()`.

### ⚡ Gestión Avanzada del Ciclo de Vida y Limpieza de Procesos
- **Terminación Total de Procesos (In-App y System Tray)**:
  - Nuevo módulo `core/process_cleanup.py` que implementa `terminate_all_processes(force=True)`.
  - Detiene ordenadamente hilos de captura, transmisiones activas y previsualizaciones, y elimina árboles de procesos huérfanos de FFmpeg y FFplay (`taskkill /F /T` y `psutil`).
  - Libera el mutex de instancia única (`single_instance_lock`), finaliza el System Tray y llama a `os._exit(0)`.
- **Restablecimiento a Valores de Fábrica ("Factory Reset")**:
  - Nuevo endpoint protegido `POST /api/system/factory_reset` con confirmación explícita.
  - Elimina de forma segura la configuración, respaldos, archivos de registro y directorios de almacenamiento en `%LOCALAPPDATA%\RTMS\`.
- **Renombramiento a "Detención Global"**:
  - Sustituida la nomenclatura alarmista por `⏹️ Detener Todo` / `Detención Global` en la interfaz.

---

## RTMS v2.2.3 — Seguridad y Mitigación de Vulnerabilidades (Dependabot)
*(2026-09-15)*

### 🛡️ Seguridad y Remediación de Vulnerabilidades
- **Mitigación Integral de 28 Alertas de Dependabot**:
  - **Pillow (`>=12.3.0`)**: Mitigadas 18 vulnerabilidades, incluyendo inyección de comandos en `WindowsViewer` sobre Windows y corrupción de memoria en filtros de imagen.
  - **Starlette (`>=1.3.1` / `1.6.0`)**: Mitigadas 6 vulnerabilidades, destacando protección contra SSRF y fugas de NetNTLM vía rutas UNC en `StaticFiles`.
  - **Jinja2 (`>=3.1.6`)**: Mitigadas 3 vulnerabilidades de escape de sandbox en plantillas.
  - **Pytest (`>=9.0.3`)**: Mitigada vulnerabilidad en gestión de carpetas temporales compartidas.
- **Actualización y Sincronización del Ecosistema**:
  - FastAPI (`0.141.1`), Uvicorn (`0.53.0`), Pydantic (`2.13.5`), Psutil (`7.2.2`), Ruff (`0.16.7`) y PyInstaller (`6.22.3`).

### 💻 Interfaz de Usuario y Dashboard
- **Layout de Codificador de Video**: Reestructurado el selector de codificador de hardware (`#config-encoder`) en una fila de ancho completo (`100%`) para evitar recortes de nombres de GPU (NVENC, QSV, AMF).
- **Copiado Rápido de `mpegts`**: Chip interactivo `.btn-copy-chip` para copiar el valor `mpegts` con un solo clic.

---

## RTMS v2.2.2 — Blindaje de Seguridad, Estabilidad en Streaming y Auditoría Integral
*(2026-09-15)*

### 🔒 Criptografía y Protección de Datos
- **Corrección Crítica en Desencriptación DPAPI**: `unprotect_secret()` retorna cadena vacía o genera `SecretDecryptionError` protegiendo contra fugas de texto cifrado.
- **Filtro Global de Secretos y Sanitización**: `SecretFilter` y `sanitize_url()` integrados en todos los loggers y respuestas API.
- **Tickets Efímeros para Previsualización MJPEG**: `PreviewTicketManager` (TTL 60s) con consumo único estricto para proteger tags `<img>`.
- **Headers de Seguridad HTTP**: Middleware agregando `X-Content-Type-Options`, `Referrer-Policy` y `X-Frame-Options`.

### 📹 Estabilidad Multimedia y Hardware
- **Control de Concurrencia**: Semáforo global (`asyncio.Semaphore(3)`) en previsualizaciones de video.
- **Detección Dinámica de Colisión de Puertos**: Manejo y reasignación en caliente ante puertos ocupados.
- **Telemetría de GPU NVENC**: Integración de métricas directas con `nvml.dll`.

---

## RTMS v2.2.1 — Auditoría Exhaustiva y Hardening de Completitud
*(2026-09-15)*

### 🔧 Correcciones Críticas de Estabilidad
- **Aislamiento en Pruebas**: Parcheo localizado con `monkeypatch` evitando mutaciones globales en `os.path`.
- **Tolerancia a Puertos Corruptos**: Manejo seguro en deserialización de configuración.
- **Timeouts en Comandos de Sistema**: Protección con `timeout=15` en invocaciones nativas a `powercfg`, `powershell` y `netsh`.
- **Validación de Passphrases SRT**: Regla estricta entre 10 y 79 caracteres conforme al estándar SRT.

---

## RTMS v2.2.0 — Telemetría en Vivo de GPU y Red (Producción)
*(2026-09-14)*

### 📊 Monitorización en Tiempo Real
- **Métricas de GPU con NVML Directo**: Detección nativa de GPU NVIDIA, uso de cómputo (0-100%) y VRAM usada/total con latencia <1ms.
- **Métricas de Red por Segundo**: Cálculo de ancho de banda entrante/saliente (`sent_kbps`, `recv_kbps`) con protección de rollover.
- **HUD Integrado**: Despliegue en vivo en la barra superior con tooltips detallados.

---

## RTMS v2.1.0 — Vista Previa de Video On-Demand y Optimizaciones
*(2026-09-14)*

### 🎥 Vista Previa y Detección PnP
- **Streaming MJPEG On-Demand**: Previsualizaciones en tiempo real sin multiplexor `-tee` bloqueante y consumo 0% en reposo.
- **Modo Encuadre**: Captura de cuadros individuales para calibrar cámaras detenidas.
- **Detección de Cámaras Virtuales de IA**: Detección inteligente de cámaras virtuales (NVIDIA Broadcast) para evitar consumo espurio de GPU.

---

## RTMS v2.0.4 — Seguridad y Hardening Criptográfico
*(2026-09-14)*

- **Cifrado Windows DPAPI**: Cifrado transparente de claves en disco en `config.json`.
- **Sanitización de URLs y Comandos**: Enmascaramiento automático de credenciales.
- **Verificación Criptográfica SHA-256**: Descarga y validación automática de sumas oficiales de FFmpeg.

---

## RTMS v2.0.3 — Seguridad, Watchdog Resiliente y Calidad de Código
*(2026-09-14)*

- **CORS Estricto y Token Local**: Blindaje contra ataques CSRF localhost vía cabecera obligatoria `X-RTMS-Token`.
- **Watchdog con Backoff Progresivo**: Reintentos inteligentes con reseteo tras 60 segundos de transmisión estable.
- **Rotación Automática de Logs**: `RotatingFileHandler` de 5 MB para operaciones continuas 24/7.

---

## RTMS v2.0.2 — Protocolo SRT por Defecto, Ultra Baja Latencia y System Tray
*(2026-09-14)*

- **SRT Listener Nativo**: Configuración de ultra baja latencia (`zerolatency`).
- **Mutex de Instancia Única**: Prevención de múltiples procesos concurrentes mediante Win32 Mutex.
- **System Tray de Windows**: Minimización a segundo plano con menú interactivo vía `pystray`.

---

## RTMS v2.0.0 — Versión Inicial
*(2026-07-03)*

- Arquitectura desacoplada: backend FastAPI + ventana de escritorio WebView2 + motor FFmpeg DirectShow.
- Transmisión en protocolos SRT y UDP Multicast.
- Optimización de planes de energía de Windows y reglas de Windows Firewall.
