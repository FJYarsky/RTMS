# Changelog — RTMS (Real-Time Multicam System)

Todas las modificaciones notables de este proyecto se documentan en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y el versionado sigue [Semantic Versioning](https://semver.org/lang/es/).
## [2.2.6] — 2026-09-17

### Sistema de Pruebas Profundas, Digestión de Video y Simulación de Cámaras Virtuales
- **Motor de Diagnóstico y Digestión de Video (`core/ffmpeg_tester.py`)**:
  - Implementada la clase `VideoReceiverDigest` que conecta a flujos SRT y UDP con `-progress pipe:1` y decodifica cuadros en tiempo real, midiendo FPS decodificados reales, bitrate promedio, estabilidad temporal, cuadros caídos y capturando errores de sintaxis del bitstream H.264.
  - Implementada la clase `VirtualCameraSource` que genera fuentes virtuales calibradas (`testsrc2`, barras SMPTE, reloj OSD) a cualquier resolución (720p, 1080p, 4K) y framerate (30fps, 60fps) mediante FFmpeg `lavfi` para pruebas controladas independientes de hardware físico.
  - Implementada la suite `FFmpegDiagnosticSuite` con tests automatizados de binarios, aceleración por hardware (`h264_nvenc`, `libx264`), análisis de capacidades DirectShow y entablado de conexiones.
- **Herramienta de Consola CLI (`scripts/test_ffmpeg_pipeline.py`)**:
  - Nueva herramienta de diagnóstico integral por terminal con salida formateada y banderas de control (`--all`, `--srt`, `--udp`, `--bench`, `--camera`, `--virtual-cam`).
- **Tests de Integración en Vivo para Pytest (`tests/test_ffmpeg_live.py`)**:
  - Incorporados 5 tests automatizados de integración que validan el soporte de protocolos, benchmarking de codificadores, handshake SRT con contraseña, rechazo seguro y streaming UDP a 1080p60 sin pérdidas.

### Correcciones Críticas de Conexión SRT y Ciclo de Vida
- **Copia Fiable de URL de Conexión (`GET /api/stream/{device_path}/connect_url`)**:
  - Incorporado el endpoint protegido `/api/stream/{device_path}/connect_url` en `api/routes.py` que genera la URL exacta de conexión para OBS Studio y vMix incluyendo la contraseña requerida si está activa.
  - Actualizado `gui/static/app.js` (`copyUrlByIndex`) para consultar este endpoint y copiar al portapapeles la URL 100% funcional.
  - Resuelto de raíz el error `ERROR:UNSECURE (Password required or unexpected)` que ocurría al intentar conectar clientes externos sin conocer la clave secreta auto-generada.
- **Resiliencia y Reanudación Inmediata de Listener SRT**:
  - En `core/ffmpeg_mgr.py`, el Watchdog detecta cuando un proceso FFmpeg en modo listener finaliza debido a la desconexión del cliente SRT (`-5 I/O error`) y reinicia el listener inmediatamente sin aplicar contadores de fallo ni retardos de *backoff*, asegurando que el flujo esté siempre disponible para nuevas conexiones o reconexiones de OBS.

### Optimización y Estabilidad de UDP a 1080p @ 60 FPS
- **Ampliación de Buffer de Socket a 4 MB**:
  - En `core/ffmpeg_mgr.py` (`build_multicast_url`), el parámetro `buffer_size` se incrementó de `65535` (64 KB) a `4194304` (4 MB) con `overrun_nonfatal=1` y `fifo_size=50000000`, eliminando el descarte silencioso de datagramas UDP por desbordamiento de socket en Windows.
- **Inyección Periódica de Cabeceras H.264 (`repeat-headers` y `dump_extra`)**:
  - Añadido `-x264-params repeat-headers=1` para `libx264` y `-forced-idr 1` para `h264_nvenc`, junto al filtro de multiplexación `-bsf:v dump_extra` para MPEG-TS. Garantiza que cualquier receptor que sintonice a mitad de transmisión reciba inmediatamente SPS/PPS sin errores de decodificación (`non-existing PPS 0 referenced`).
- **Soporte Nativo de Fuentes Virtuales en RTMS**:
  - `build_command` en `core/ffmpeg_mgr.py` ahora admite cámaras virtuales con prefijo `virtual://` o `testsrc` generando patrones `testsrc2` en tiempo real para entornos de prueba o estudio sin capturadora física.

## [2.2.5] — 2026-09-16

### Desbloqueo Automático Mark-of-the-Web (Zone.Identifier) y Runtime .NET
- **Desmarque Automático de Binarios (`unblock_app_binaries`)**:
  - Implementada la función nativa Win32 `unblock_app_binaries()` en `core/system_env.py` que recorre el directorio base de la aplicación al arrancar y elimina los flujos alternativos NTFS `:Zone.Identifier` (`ZoneId=3`) que Windows añade al descargar el archivo `.zip` de releases desde navegadores como Chrome o Edge.
  - Resuelve de raíz el bloqueo de seguridad de .NET Framework (CAS) que impedía a `clr_loader` y `pythonnet` resolver `Python.Runtime.Loader.Initialize`, eliminando por completo la apertura involuntaria en el navegador web.
- **Configuración de Runtime CLR (`rtms.exe.config`)**:
  - Incorporado el archivo de configuración `rtms.exe.config` con la directiva `<loadFromRemoteSources enabled="true"/>` y activación de runtime v4.0 (SKU .NETFramework 4.6.2), autorizando explícitamente la carga de ensamblados .NET descargados.
- **Empaquetado Completo de `clr_loader`**:
  - Actualizado `build_portable.bat` para incluir `--hidden-import=clr_loader`, `--hidden-import=clr_loader.ffi`, `--hidden-import=clr_loader.ffi.netfx` y `--collect-all=clr_loader`, garantizando que `ClrLoader.dll` y todos los componentes nativos se empaqueten dentro de la distribución portable.

### Responsividad Instantánea y Desacoplamiento Asíncrono del System Tray
- **Despacho Asíncrono Estricto (`_dispatch_async`)**:
  - Rediseñados todos los callbacks del menú contextual en `core/tray_icon.py` (`_show`, `_stop_all`, `_terminate`, `_about`, `_exit`) para despacharse inmediatamente en hilos de trabajo independientes (`daemon=True`).
  - La bomba de mensajes Win32 de `pystray` (`GetMessage` / `DispatchMessage`) nunca se bloquea, asegurando que el menú contextual se despliegue al instante (<1 ms) con las coordenadas de pantalla exactas bajo el cursor del ratón.
- **Control de Estado de Ventana Nativa (`_main_window_ready`)**:
  - Incorporada la bandera de estado `_main_window_ready` en `main.py` para sincronizar la inicialización efectiva del motor WebView2 (`webview.start(func=on_window_ready, gui="edgechromium")`).
  - Eliminado el bloqueo y timeout síncrono de 10 a 20 segundos (`events.shown.wait(10)`) que ocurría cuando `show_window_from_tray()` o `show_about_from_tray()` intentaban interactuar con ventanas inactivas o en error.
  - En caso de fallo de pywebview, la referencia `_main_window` se restablece a `None` y el acceso se redirige limpiamente al navegador sin retardos ni cuelgues.

## [2.2.4] — 2026-09-16

### Interfaz de Escritorio Nativa y Empaquetado Portable (WebView2)
- **Corrección Crítica de Ventana Nativa en Release Portable**:
  - En la distribución portable generada por PyInstaller, se empaquetan las dependencias nativas de `pythonnet` (`--hidden-import=pythonnet`, `--collect-all=pythonnet`) y se copian automáticamente todas las DLLs de WebView2 (`Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll` y la carpeta de arquitecturas `runtimes/`) junto a `icon.ico` hacia la raíz y `_internal` de `dist/rtms/`.
  - Se elimina el fallo silencioso que forzaba a la aplicación a abrirse en el navegador por defecto (Google Chrome) en lugar del entorno de escritorio nativo con aceleración Edge WebView2.
- **Corrección de Diseño y Visualización de Métricas del HUD**:
  - Corregida la alineación horizontal flexible (`display: flex; flex-direction: row;`) de los indicadores de telemetría (CPU, GPU, RAM, Red, Bitrate) en la barra superior (`header`), resolviendo el apilamiento vertical y desbordamiento tras la adición del botón de detención y salida.
  - Incorporadas reglas de adaptabilidad responsiva con *media queries* para garantizar una visualización impecable en ventanas compactas.
- **Eliminación de Ventanas Duplicadas y Pestañas Periódicas**:
  - `show_window_from_tray()` en `main.py` ahora valida la existencia de la ventana nativa (`_main_window`) e invoca exclusivamente `show()` y `restore()`. Se eliminó cualquier invocación accidental a `webbrowser.open()` cuando el motor nativo está activo.
  - Sincronización robustecida en `acquire_single_instance_lock()` para que segundas instancias pasen el foco a la ventana existente mediante señalización IPC en lugar de desplegar interfaces concurrentes.

### Gestión Avanzada del Ciclo de Vida y Limpieza de Procesos
- **Terminación Total de Procesos (In-App y System Tray)**:
  - Nuevo módulo `core/process_cleanup.py` que implementa `terminate_all_processes(force=True)`.
  - Detiene ordenadamente hilos de captura, transmisiones activas y previsualizaciones, y elimina árboles de procesos huérfanos de FFmpeg y FFplay (`taskkill /F /T` y `psutil`).
  - Libera el mutex de instancia única (`single_instance_lock`), finaliza el System Tray y llama a `os._exit(0)`.
  - Botón `⚡ Salir / Finalizar` en la barra superior y en la pestaña de Sistema con diálogo modal de confirmación.
  - Opción de menú contextual `Finalizar todos los procesos` en la bandeja del sistema.
  - Nuevo endpoint protegido `POST /api/system/shutdown`.
- **Restablecimiento a Valores de Fábrica ("Factory Reset")**:
  - Nuevo endpoint protegido `POST /api/system/factory_reset` que requiere confirmación explícita (`confirm: true`).
  - Elimina de forma segura la configuración (`rtms_config.json*`), copias de respaldo, archivos de registro (`rtms.log*`) y directorios de almacenamiento en `%LOCALAPPDATA%\RTMS\`.
  - Ejecuta la terminación total de procesos para garantizar que el siguiente arranque sea 100% limpio como una instalación nueva.
  - Botón `🗑️ Restablecer a Valores de Fábrica` en la sección de Sistema con modal de confirmación y advertencia.
- **Renombramiento de "Parada de Emergencia" a "Detención Global"**:
  - Sustituida la nomenclatura alarmista por `⏹️ Detener Todo` / `Detención Global` en la interfaz, adaptando el color del botón a tono ámbar sobrio.

### Integración y Rediseño del System Tray
- **Opción "Acerca de RTMS" en la Bandeja del Sistema**:
  - Incorporada la opción de menú `Acerca de RTMS` en `core/tray_icon.py`, permitiendo invocar el modal interactivo de información y créditos de autor en la ventana nativa o un cuadro de diálogo nativo Win32 en caso de ejecución en segundo plano.
- **Icono Vectorial Moderno**: Rediseñado el icono por defecto en `core/tray_icon.py` con diseño de esquinas redondeadas en color grafito oscuro (`#1E293B`), lente concéntrico cian (`#06B6D4` / `#0891B2`) y punto indicador de captura.
- **Menú Contextual Enriquecido**: Agregadas las acciones `Detener todas las transmisiones`, `Finalizar todos los procesos` y tooltip dinámico con versión del sistema.
- **Restauración Fiable**: El botón `Mostrar RTMS` enfoca de forma consistente la ventana nativa de la aplicación.

### Monitoreo de Plataforma Windows y Auditoría Integral
- **Detalles Completos de Entorno Windows**:
  - Detección de edición de Windows, Build Number, UBR (Update Build Revision) y arquitectura (64-bit / ARM64) mediante consulta directa al Registro de Windows (`SOFTWARE\Microsoft\Windows NT\CurrentVersion`).
  - Exposición en `/api/system/status`, integración en el HUD superior y tabla de diagnóstico del sistema.
- **Resolución de Auditorías Técnicas y Blindaje del Sistema**:
  - Persistencia de `ignored_devices` en `core/config_mgr.py` para evitar que el hotplug de DirectShow reactive cámaras eliminadas.
  - Corrección de `SecretFilter` para soportar argumentos `%s` sin generar excepciones `TypeError`.
  - Tickets efímeros de preview de uso único (single-use) e invalidación por dispositivo con límite de capacidad estricto (cap a 100).
  - Documentación detallada en `docs/TROUBLESHOOTING.md` sobre contención de sockets en modo SRT Listener.
  - Incorporación de `CODE_OF_CONDUCT.md` bajo el estándar Contributor Covenant v2.1.
  - Eliminación absoluta de datos personales de contacto no profesionales en el 100% de los archivos.
  - Estandarización permanente de encabezados y descripciones funcionales en todos los módulos.
  - 93 pruebas unitarias y de integración pasando al 100% y 0 errores de linter.

## [2.2.3] — 2026-09-15

### Seguridad y Mitigación de Vulnerabilidades (Dependabot)
- **Remediación Integral de 28 Alertas de Dependabot**:
  - **Pillow (`>=12.3.0` / lockfile `12.3.0`)**: Mitigadas 18 vulnerabilidades (12 High, 6 Medium), incluyendo CVE-2026-55798 (inyección de comandos en `WindowsViewer` sobre Windows), corrupción de memoria por heap out-of-bounds write en `ImageFilter.RankFilter`, `paste()` y `crop()`, y bypass de bombas de descompresión en fuentes tipográficas y PSDs.
  - **Starlette (`>=1.3.1` / lockfile `1.6.0`)**: Mitigadas 6 vulnerabilidades (3 High, 2 Medium, 1 Low), destacando CVE-2026-48818 (SSRF y fuga de credenciales NetNTLM en Windows vía rutas UNC en `StaticFiles`), mitigando riesgos locales en la red LAN del operador, además de DoS cuadrático por Range headers en `FileResponse` y desbordamiento en `request.form()`.
  - **Jinja2 (`>=3.1.6` / lockfile `3.1.6`)**: Mitigadas 3 vulnerabilidades de escape de sandbox (CVE-2024-56326, CVE-2024-56201, CVE-2025-27516) mediante referencias indirectas y filtros a `format`.
  - **Pytest (`>=9.0.3` / lockfile `9.1.1`)**: Mitigada vulnerabilidad en gestión de carpetas temporales compartidas (CVE-2025-71176).
  - **Ecosistema Sincronizado**: Actualizadas dependencias asociadas a versiones estables y compatibles: FastAPI (`0.141.1`), Uvicorn (`0.53.0`), Pydantic (`2.13.5`), Psutil (`7.2.2`), Ruff (`0.16.7`) y PyInstaller (`6.22.3`).

### Pipelines de Integración Continua (GitHub Actions CI)
- **Reparación del Pipeline de CI**: Eliminadas importaciones redundantes e inactivas en `tests/test_fastapi_headless.py` que causaban fallo inmediato en la regla `F401` de Ruff en GitHub Actions.
- **Consolidación de PRs de Dependabot**: Unificación de 7 PRs parciales en un único conjunto de dependencias verificado y libre de vulnerabilidades.

### Interfaz de Usuario y Experiencia de Operación (Dashboard)
- **Corrección de Layout en Codificador de Video**: Reestructurado el formulario modal para ubicar el selector de codificador de hardware (`#config-encoder`) en una fila dedicada inferior de ancho completo (`100%`), eliminando definitivamente el recorte de etiquetas descriptivas de GPU (NVENC, QSV, AMF, CPU).
- **Copiado Rápido de `mpegts`**: Implementado chip interactivo `.btn-copy-chip` en la Guía de Configuración de OBS Studio que permite copiar el valor `mpegts` al portapapeles con un solo clic y retroalimentación inmediata vía toast.
- **Portapapeles Seguro y Asíncrono**: Modernizado el servicio de copia en `app.js` con soporte prioritario para la API nativa `navigator.clipboard` y degradación elegante.

## [2.2.2] — 2026-09-15

### Seguridad y Blindaje Criptográfico (DPAPI & Secretos)
- **Corrección Crítica en Desencriptación DPAPI**: `unprotect_secret()` ahora retorna cadena vacía o genera `SecretDecryptionError` en lugar de retornar la cadena de error o el texto cifrado original en caso de fallo de `CryptUnprotectData`.
- **Filtro Global de Secretos y Sanitización de URLs**: Implementado `SecretFilter` en todos los loggers y la función `sanitize_url()` para enmascarar automáticamente credenciales en URLs SRT en logs, APIs y memoria.
- **Protección Estricta en Exportación de Configuración**: `GET /api/config/export` fuerza `safe_mode=True` de forma incondicional. Nuevo endpoint `POST /api/config/export/full` requiere confirmación explícita (`confirm_export_secrets: true`) para volcar contraseñas.
- **Tickets Efímeros para Vista Previa MJPEG**: Creado `PreviewTicketManager` (TTL 60s) accesible en `POST /api/preview/ticket`, eliminando la exposición de tokens de sesión globales en tags `<img>` y URLs del historial de navegación.
- **Headers de Seguridad HTTP**: Middleware global agregando `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` y `X-Frame-Options: SAMEORIGIN`.

### Estabilidad del Motor Multimedia y Previsualización
- **Control de Concurrencia en Vista Previa**: Semáforo global (`asyncio.Semaphore(3)`) y asignación exclusiva de ranura por cámara, retornando HTTP 429 ante sobrecarga.
- **Prevención de Desbordamiento de Memoria en MJPEG**: Safety cap de 4 MB en el buffer de delimitadores JPEG (`--frame`) para evitar fugas de memoria ante flujos corruptos.
- **Liberación Inmediata de Dispositivos DirectShow**: Manejo de `asyncio.TimeoutError` con `kill()` forzado y espera de terminación en `get_snapshot_frame()` para evitar bloqueos del driver de cámara.
- **Cierre Unificado de Servidor y Procesos**: Invocación garantizada de `stream_manager.stop_all()`, `preview_manager.stop_all()` y `telemetry_service.shutdown()` tanto en el lifespan de FastAPI como en el handler `on_closed()`.
- **Taxonomía de Estados y Categorización de Errores**: Estados explícitos de ciclo de vida (`STARTING`, `RUNNING`, `RECOVERING`, `STOPPING`, `DISCONNECTED`, `MANUAL_INTERVENTION_REQUIRED`), mapeo a `ErrorCategory` y limpieza garantizada de tareas asíncronas de recuperación.
- **Detección Dinámica de Colisión de Puertos**: Detección en logs de FFmpeg de fallos de socket (`bind failed`, `address already in use`) con reasignación y reintento en caliente.
- **Disambiguación de Cámaras Idénticas**: `generate_stable_camera_id` utiliza la ruta física normalizada completa de DirectShow para diferenciar dispositivos con idéntico identificador VID/PID.
- **Eliminación Permanente de Cámaras**: Nuevo endpoint `DELETE /api/stream/{device_path:path}` con opción en la interfaz gráfica para descartar cámaras persistidas.

### Telemetría de Hardware y Optimización
- **Uso de Codificador NVENC**: Incorporada la métrica de utilización del motor de codificación de video mediante `nvmlDeviceGetEncoderUtilization`.
- **Estructuras NVML a Nivel de Módulo**: Reubicadas estructuras `ctypes` fuera del método de recolección para evitar overhead en cada sondeo.
- **Soporte Multi-GPU**: Parámetro configurable de índice de dispositivo gráfico para equipos con múltiples GPUs dedicadas.
- **Diferenciación de Ancho de Banda**: Separación explícita entre el tráfico de red total del sistema operativo y el bitrate emitido por los streams de RTMS.
- **Degradación Suave y Apagado Limpio**: Desactivación automática tras 5 fallos consecutivos de sondeo GPU, exclusión mutua mediante `threading.Lock()` y apagado limpio con `nvmlShutdown()`.

### Interfaz de Usuario y Empaquetado
- **Operatividad 100% Offline / Air-Gapped**: Removida la dependencia externa de Google Fonts en `index.html`; tipografía nativa multiplataforma optimizada.
- **Carga Perezosa de Módulos GUI**: Importaciones seguras de `webview` y `pystray` para compatibilidad en entornos headless y servidores.
- **Verificación Estricta en Empaquetado y CI**: Validación obligatoria de `bin/ffmpeg.exe` y `bin/ffplay.exe` previa al empaquetado, suite de CI con cobertura y workflow de publicación automática de releases en GitHub.

## [2.2.1] — 2026-09-15

### Auditoría Exhaustiva y Hardening de Completitud
- **Aislamiento Seguro en Tests**: Reemplazado mock global de `os.path.exists` en `tests/test_command_builder.py` por parche modular con `monkeypatch`, evitando efectos colaterales en la biblioteca estándar y `asyncio`.
- **Tolerancia a Puertos Corruptos**: Manejo seguro con `try/except (ValueError, TypeError)` en `core/config_mgr.py` al deserializar puertos de cámaras, garantizando la recuperación automática ante archivos dañados.
- **Preservación Estricta de Secretos SRT**: Corrección en `/api/stream/config` para evitar la sobreescritura accidental con la máscara literal (`••••••••`) cuando el proceso se encuentra fuera de línea.
- **Prevención de Bloqueos por Subprocesos**: Añadido `timeout=15` a todas las invocaciones de `powercfg`, `powershell` y `netsh` en `core/system_env.py` para impedir bloqueos indefinidos del sistema.
- **Detección Dinámica de WebView2Loader.dll**: Soporte dinámico en `build_portable.bat` para compilar con cualquier distribución de Python de Windows.
- **Ciclo de Vida Limpio de Procesos**: Eliminación de riesgo de procesos zombie en `core/preview_mgr.py` con `await proc.wait()` y recolección automática de instancias inactivas de `ffplay`.
- **Validación Backend de Frases de Paso SRT**: Regla de validación con Pydantic (`@field_validator`) asegurando entre 10 y 79 caracteres conforme al estándar del protocolo SRT.
- **Expansión Masiva de Suite de Pruebas**: Adición de 5 suites de pruebas unitarias (`test_secrets_mgr.py`, `test_single_instance.py`, `test_autostart.py`, `test_schemas.py`, `test_doctor.py`), alcanzando cobertura en todos los subsistemas del motor.
- **Prevención de Fugas de Descriptores de Red**: Context managers `with socket.socket(...) as s:` en `api/routes.py` y `core/doctor.py`.
- **Consistencia UI/Backend**: Sincronización del preset de máxima calidad ('best') a 6000 kbps entre el panel web y el motor de configuración.
- **Blindaje contra Inyecciones DOM (XSS)**: Escapado integral con `escapeHtml` de propiedades de cámara (`resolution`, `protocol`, `encoder`, `url`) en la interfaz web (`gui/static/app.js`).
- **Validación Estricta de Importación**: Validador Pydantic en `ImportConfigRequest` y verificación robusta de tipos en `core/config_mgr.py:import_config()`.
- **Supresión de Ventanas de Consola en Diagnóstico**: Bandera `_WIN_FLAGS` incorporada en `core/doctor.py` para ejecuciones limpias de subprocesos FFmpeg.
- **Seguridad Criptográfica en PowerShell**: Forzado explícito de TLS 1.2 / TLS 1.3 en `scripts/setup_binaries.ps1` para descargas seguras de binarios.
- **Suite de Pruebas Ampliada a 68 Tests**: 100% de pruebas automáticas aprobadas.

## [2.2.0] — 2026-09-14

### Telemetría de Hardware y Red (HUD en Vivo)
- **Métricas de GPU en Tiempo Real (NVML Directo)**: Implementado `GpuTelemetryReader` en `core/telemetry.py` que consulta directamente la biblioteca nativa `nvml.dll` mediante `ctypes`. Proporciona porcentaje de utilización gráfica (0-100%), consumo de memoria de video (VRAM usada y total en MB), y nombre del modelo de hardware GPU con latencia sub-milisegundo (<1ms), sin dependencias externas de Python ni sobrecarga de subprocesos.
- **Tolerancia a Fallos y Conmutación Suave de GPU**: Si el sistema carece de tarjeta gráfica NVIDIA o controladores compatibles, el HUD conmuta automáticamente a estado `N/A` con un tooltip informativo, previniendo errores o excepciones.
- **Monitorización de Rendimiento de Red**: Implementado `NetworkTelemetryTracker` en `core/telemetry.py` utilizando `psutil.net_io_counters()`. Calcula tasas de transferencia instantáneas en kilobits/megabits por segundo (`sent_kbps`, `recv_kbps`, `total_kbps`), protegido contra condiciones de carrera (`threading.Lock`) y reinicio de contadores del sistema operativo.
- **HUD Header Expandido**: Integrados los nuevos indicadores visuales `GPU` y `RED` en la barra superior junto a `CPU`, `RAM` y `BITRATE`. Incluye tooltips enriquecidos con desglose de subida `↑` / bajada `↓` y VRAM en megabytes.
- **Suite de Pruebas de Telemetría**: Añadido `tests/test_telemetry.py` con 5 nuevas pruebas unitarias y de integración que validan el cálculo de tasas de red, protección de rollover, modo seguro de GPU y el payload de `/api/system/metrics`.

## [2.1.0] — 2026-09-14

### Nuevas Características y Monitorización
- **Vista Previa de Video On-Demand (Consumo Cero en Reposo)**: Implementado `core/preview_mgr.py` con Streaming MJPEG asíncrono para la Web UI y monitor nativo de ultra-baja latencia con `FFplay`. Desacoplado 100% de la transmisión principal (sin multiplexor `-tee` bloqueante) y con liberación inmediata de recursos (0.00% CPU/GPU) al cerrar el visor.
- **Modo Encuadre para Cámaras Detenidas**: Captura DirectShow directa de un cuadro estático cuando la cámara no está emitiendo para facilitar el encuadre y enfoque previo al evento.
- **Detección y Clasificación de Cámaras Virtuales**: Detección y clasificación automática de `NVIDIA Broadcast` y otras cámaras virtuales de IA, con `auto_start: false` para evitar consumo espurio de Tensor Cores y GPU 3D en segundo plano.
- **Indicador de Codificador Activo y Modo Fallback**: La tarjeta de cámara ahora refleja dinámicamente el codificador real en uso (e.g. `auto (h264_nvenc)`) y destaca en color ámbar el estado si está operando bajo `Modo CPU Fallback`.

### Optimizaciones de Rendimiento y Hardware
- **Caché Global de Encoders (`HardwareCapabilityDetector`)**: Detección singleton de encoders disponibles en hardware (`NVENC`, `QSV`, `AMF`, `libx264`), eliminando la ejecución repetida de subprocesos de prueba de FFmpeg.
- **Deduplicación de I/O en Disco (DPAPI)**: Resuelto el bug de escrituras continuas a disco cada 20 segundos provocado por la aleatoriedad de la sal criptográfica de `CryptProtectData`. La comparación ahora se realiza contra la configuración lógica en memoria.
- **Caché TTL para Sondeo de IP Local**: Caché de 30 segundos en `get_local_ip()` para evitar la apertura continua de sockets de red y sondeos de `psutil` durante el refresco de telemetría de la UI.

### Estabilidad y Sistema Operativo (Windows)
- **Prevención Nativa de Suspensión (`SetThreadExecutionState`)**: Implementado `acquire_stay_awake()` y `release_stay_awake()` en el ciclo de vida de la aplicación para evitar que las laptops entren en suspensión durante eventos en vivo, incluso sin elevación de privilegios de Administrador.
- **Deduplicación de Reglas de Firewall**: Verificación previa con `netsh advfirewall firewall show rule` antes de añadir la regla `RTMS_Media_Ports`, evitando reglas duplicadas o acumuladas.
- **Manejo Seguro de Handles Win32 (64-bit)**: Tipado explícito de `wintypes.HANDLE` y `ctypes.WinDLL(..., use_last_error=True)` en `core/single_instance.py` para prevenir truncamientos de punteros de 64 bits en el Mutex de instancia única.

### Seguridad, Empaquetado y Testing
- **Empaquetado Seguro (`build_portable.bat`)**: Exclusión rigurosa de `config.json` y copias `.bak` del paquete distribuible `dist/rtms/`, incluyendo únicamente la plantilla limpia `config.example.json`.
- **Avisos de Terceros y Licencias**: Creación de `THIRD_PARTY_NOTICES.md` documentando las licencias GPLv3 / LGPL de FFmpeg y FFplay.
- **Aislamiento Total de Tests**: Creación de fixture autouse en `conftest.py` que redirige las rutas de configuración a directorios temporales `tmp_path`, garantizando que la ejecución de `pytest` jamás modifique el entorno de producción.
- **Token Seguro en Vista Previa**: El verificador de token de seguridad soporta validación en tiempo constante (`secrets.compare_digest`) y parámetros de consulta para alimentar elementos de imagen en el navegador sin comprometer la seguridad contra ataques Drive-By.

---

## [2.0.4] — 2026-09-14

### Seguridad y Hardening (P0 & P1)
- **Sanitización Estricta de Secretos**: Creación de `core/sanitizer.py` para enmascarar automáticamente cualquier `passphrase=...` o token en comandos de FFmpeg, buffers de memoria y archivos de log.
- **Protección Integral de Endpoints Sensibles**: Extensión del middleware de autenticación `X-RTMS-Token` a endpoints de lectura (`GET /api/status`, `/api/stream/logs`, `/api/system/metrics`, `/api/power/status`), dejando `/healthz` como único endpoint público.
- **Cifrado en Disco de Passphrases (Windows DPAPI)**: Integración de `core/secrets_mgr.py` utilizando Windows DPAPI nativo (`CryptProtectData`) para cifrar frases de paso en reposo dentro de `config.json`.
- **Verificación Criptográfica SHA256 de FFmpeg**: Actualización de `scripts/setup_binaries.ps1` para descargar y validar el hash SHA256 oficial de Gyan.dev antes de descomprimir binarios.
- **Escape Seguro de URLs SRT**: Parámetros de URL codificados mediante `urllib.parse.quote_plus` para evitar inyecciones por caracteres especiales.
- **Frontend Seguro contra Inyecciones DOM**: Reemplazo de interpolaciones directas a `innerHTML` con `textContent` y función `escapeHtml()` en `gui/static/app.js`.

### Ciclo de Vida y Streaming (P0)
- **Shutdown Unificado y Eliminación de `os._exit(0)`**: Protocolo limpio de parada en `StreamManager.stop_all()`. FFmpeg recibe señal `b'q'` a `stdin`, con período de gracia de 2.5s antes de `terminate()` y fallback final a `kill()`. Cierre ordenado de Uvicorn y salida mediante `sys.exit(0)`.
- **Corrección de Carrera en Fallback GPU $\rightarrow$ CPU**: Bloqueo de exclusión mutua (`asyncio.Lock`) por cámara y método explícito `_fallback_to_cpu()` que garantiza la detención del proceso de GPU antes de inicializar `libx264`.
- **Aislamiento de Encoder por Dispositivo**: Fallos transitorios de GPU en un flujo no degradan a las demás cámaras a CPU.
- **Opción `zerolatency` 100% Funcional**: Conmutación real de flags de multiplexado MPEG-TS (`-muxdelay 0`, `-flush_packets 1`), descarte de paquetes SRT (`tlpktdrop=1/0`) y sintonización de encoder.

### Robustez y Arquitectura (P1 & P2)
- **ConfigManager Atómico y Resiliente**: Escritura segura en `.tmp`, `fsync`, copias de respaldo continuas `.bak` y framework de migraciones automáticas (`migrate_config`).
- **Identidad Estable de Cámaras (`camera_id`)**: Asignación de identificadores deterministas (UUID v5) desacoplados de la ruta física del bus USB.
- **Gestor Inteligente de Puertos (`PortManager`)**: Detección activa de sockets en uso mediante bind de SO (rango 9000-9200) y reciclaje de puertos liberados.
- **Watchdog No Bloqueante**: Evaluación independiente de reintentos mediante marca temporal (`next_retry_at`) sin suspender la supervisión del resto de flujos.
- **Validación Estricta con Pydantic**: Esquemas enriquecidos con tipos `Literal` y restricciones numéricas con `Field(ge=..., le=...)`.
- **Reporte Estructurado de Optimizaciones Windows**: `setup_windows_environment()` reporta con precisión el estado real (`ok`, `partial`, `failed`) de cada directiva.
- **Fábrica `create_app()` y Versionado Centralizado**: Instanciación desacoplada en `main.py` y fuente única de verdad en `core/__version__.py`.
- **Separación de Dependencias**: División entre `requirements.txt` (producción) y `requirements-dev.txt` (testing y dev).

### Diagnóstico, Soporte y Herramientas (P3)
- **Herramienta de Diagnóstico CLI (`RTMS Doctor`)**: Implementado `core/doctor.py` con 8 verificaciones automáticas de sistema, hardware y red.
- **Copia de Seguridad y Restauración en UI**: Funcionalidad para exportar e importar configuraciones completas en JSON desde el panel web.
- **Notificación Proactiva de Fallo**: Alerta visual destacada en la tarjeta de cámara ante el agotamiento de reintentos máximos.
- **Documentación Técnica Avanzada**: Creación de `docs/HARDWARE.md` y `docs/TROUBLESHOOTING.md`.
- **Suite de Pruebas Ampliada**: Cobertura expandida a 25 tests automatizados con `pytest` y validación estricta de linter con `ruff`.

---

## [2.0.3] — 2026-09-14

### Seguridad y Hardening
- **CORS Restringido**: Eliminado el comodín `allow_origins=["*"]` con credenciales. Ahora restringido estrictamente al origen dinámico local `http://127.0.0.1:<puerto>` para blindar la API contra ataques Localhost CSRF / Drive-by.
- **Autenticación por Token Local (`X-RTMS-Token`)**: Generación de un token criptográfico de sesión (`secrets.token_urlsafe(32)`) inyectado en el frontend nativo y exigido como cabecera obligatoria en todos los endpoints de modificación de estado (`POST /api/*`).
- **Enmascaramiento de Contraseñas SRT**: La API `/api/status` ya no expone la `srt_passphrase` en texto plano, devolviendo en su lugar `"••••••••"` y el indicador `has_passphrase: true`.
- **Passphrase Segura por Defecto**: Las nuevas cámaras creadas con protocolo SRT generan automáticamente una contraseña segura aleatoria de 12 caracteres (`secrets.token_hex(6)`).
- **Higiene de Repositorio**: Exclusión de `config/config.json` con datos de hardware local de Git mediante `.gitignore` y provisión de `config/config.example.json` limpio.

### Robustez del Watchdog
- **Reseteo de Errores por Estabilidad**: Si un flujo opera de forma ininterrumpida en estado `RUNNING` durante más de 60 segundos, su contador `error_count` se resetea a 0 automáticamente.
- **Verificación de Desconexión Física**: Si una cámara USB es desenchufada (`is_connected == False`), el Watchdog pausa los reintentos hasta que el sondeo periódico de hardware verifique su reconexión.
- **Backoff Exponencial**: Intervalos progresivos de reintento ante fallos sucesivos (5s, 10s, 20s, 40s, hasta un máximo de 60s).

### Calidad de Código y Estabilidad
- **Rotación de Logs (`RotatingFileHandler`)**: Reemplazado `FileHandler` por rotación de archivos de 5 MB con 3 copias de seguridad para prevenir crecimiento indefinido en ejecuciones 24/7.
- **Endpoint de Salud (`/healthz`)**: Implementado endpoint ligero para supervisores de procesos del sistema operativo.
- **Suite de Pruebas Automatizadas**: Integración de `pytest` con tests unitarios para análisis de DirectShow, configuración y seguridad de la API.
- **Pipeline de Integración Continua (CI)**: Flujo de trabajo de GitHub Actions en `.github/workflows/ci.yml`.

---

## [2.0.2] — 2026-09-14

### Agregado
- Protocolo SRT por defecto con ultra baja latencia (`zerolatency`).
- Conversión universal a `-pix_fmt yuv420p` en FFmpeg para compatibilidad total con GPU (NVENC, AMF, QSV).
- Bloqueo de instancia única con Win32 Named Mutex (`single_instance.py`).
- Autoarranque desatendido individual por cámara con sincronización continua PnP.
- Minimización a la bandeja del sistema de Windows (*System Tray*) mediante `pystray`.
- Telemetría en vivo en Header (CPU %, RAM %, Bitrate) y FPS/Bitrate real por cámara.
- Botón rojo de parada de emergencia con apagado seguro (*graceful shutdown*).
- Sección colapsable para cámaras virtuales y secundarias.
- Modal "Acerca de" con información y enlaces oficiales de Joaquín Yarsky.

---

## [2.0.0] — 2026-07-03

### Versión Inicial
- Arquitectura desacoplada FastAPI + `pywebview` + FFmpeg DirectShow.
- Soporte básico de UDP Multicast y SRT.
- Optimizaciones de energía en Windows y reglas de firewall.
