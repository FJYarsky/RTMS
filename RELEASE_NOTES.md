## RTMS v2.2.6 — Corrección Crítica de Conexión SRT, Optimización UDP 1080p60 y Suite de Diagnóstico FFmpeg

### 🛠️ Corrección Crítica de Entablado de Conexión SRT y Copia de URL
- **Resolución de Rechazo por Contraseña Faltante (`ERROR:UNSECURE`)**:
  - RTMS genera passphrases criptográficas seguras al registrar cámaras, pero la interfaz web copiaba la URL `srt://IP:port?mode=caller...` omitiendo el parámetro `&passphrase=...`. Sockets externos como OBS Studio o vMix eran rechazados inmediatamente con `ERROR:UNSECURE (Password required or unexpected)`.
  - Se implementó el endpoint protegido `GET /api/stream/{device_path}/connect_url` en `api/routes.py` que calcula y devuelve la URL completa y funcional con su passphrase configurada.
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
  - 5 tests de integración en vivo añadidos a la suite oficial de Pytest, elevando la cobertura a 107 tests unitarios y de integración pasando al 100%.

## RTMS v2.2.5 — Desbloqueo Mark-of-the-Web, Ventana Nativa WebView2 y System Tray de Cero Latencia

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

## RTMS v2.2.4 — Ventana Nativa WebView2, System Tray Avanzado y Limpieza Total de Procesos

### 🖥️ Interfaz de Escritorio Nativa y Empaquetado Portable (WebView2)
- **Corrección Crítica de Ventana Nativa en Release Portable**:
  - En la distribución portable generada por PyInstaller, se empaquetan las dependencias nativas de `pythonnet` (`--hidden-import=pythonnet`, `--collect-all=pythonnet`) y se copian automáticamente todas las DLLs de WebView2 (`Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll` y la carpeta de arquitecturas `runtimes/`) junto a `icon.ico` hacia la raíz y `_internal` de `dist/rtms/`.
  - Se elimina definitivamente el fallo silencioso que forzaba a la aplicación a abrirse en el navegador por defecto (Google Chrome) en lugar del entorno de escritorio nativo con aceleración Edge WebView2.
- **Corrección de Diseño y Disposición Horizontal del HUD**:
  - Solucionada la alineación flexible de los indicadores de telemetría (CPU, GPU, RAM, Red, Bitrate) en el encabezado, eliminando el desbordamiento vertical y recorte que ocurría tras la integración del nuevo botón de detención y salida. Incorporadas reglas responsivas para anchos compactos.
- **Eliminación de Ventanas Duplicadas y Pestañas Periódicas**:
  - `show_window_from_tray()` en `main.py` valida la existencia de la ventana nativa (`_main_window`) e invoca exclusivamente `show()` y `restore()`. Se eliminó cualquier invocación accidental a `webbrowser.open()` cuando el motor nativo está activo.
  - Sincronización robustecida en `acquire_single_instance_lock()` para que segundas instancias pasen el foco a la ventana existente mediante señalización IPC en lugar de desplegar interfaces concurrentes.

### ⚡ Gestión Avanzada del Ciclo de Vida y Limpieza de Procesos
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
  - Ejecuta la terminación total de procesos para garantizar que el siguiente arranque sea 100% limpio como una primera instalación.
  - Botón `🗑️ Restablecer a Valores de Fábrica` en la sección de Sistema con modal de confirmación y advertencia.
- **Renombramiento de "Parada de Emergencia" a "Detención Global"**:
  - Sustituida la nomenclatura alarmista por `⏹️ Detener Todo` / `Detención Global` en la interfaz, adaptando el color del botón a tono ámbar sobrio.

### 🎛️ Integración y Rediseño del System Tray
- **Opción "Acerca de RTMS" en el Menú Contextual**:
  - Añadida la opción directa en el menú del System Tray para acceder a la información oficial, versión y créditos de autor, abriendo el modal en la ventana nativa o un diálogo Win32 nativo en segundo plano.
- **Icono Vectorial Moderno**: Rediseñado el icono por defecto en `core/tray_icon.py` con diseño de esquinas redondeadas en color grafito oscuro (`#1E293B`), lente concéntrico cian (`#06B6D4` / `#0891B2`) y punto indicador de captura.
- **Menú Contextual Enriquecido**: Agregadas las acciones `Detener todas las transmisiones`, `Finalizar todos los procesos` y tooltip dinámico con versión del sistema (`RTMS v2.2.4 — Real-Time Multicam System`).
- **Restauración Fiable**: El botón `Mostrar RTMS` enfoca de forma consistente la ventana nativa de la aplicación sin abrir navegadores externos.

### 🛡️ Remediación de Seguridad CodeQL (8 de 8 Alertas Cerradas)
- **Mitigación de Línea de Comandos No Controlada (#6 - Critical)**: En `core/preview_mgr.py` y `api/routes.py`, validación exhaustiva de parámetros hacia FFplay contra lista blanca de cámaras configuradas, restricción de esquemas de red (`srt`, `udp`, `http`, `https`), sanitización con expresiones regulares y aplicación de `shlex.quote`.
- **Prevención de Exposición de Información por Excepciones (#7 y #8 - Medium)**: En `core/system_env.py`, supresión del flujo de excepciones hacia respuestas HTTP en endpoints `/api/power/*`, preservando la topología interna del sistema.
- **Enlace Seguro de Sockets en Loopback (#3, #4 y #5 - Medium)**: En `core/port_mgr.py` y fixtures de prueba, enlace de sockets de sondeo exclusivamente a `127.0.0.1` en vez de `0.0.0.0`.
- **Restricción de Permisos en Flujo de CI (#1 y #2 - Medium)**: En `.github/workflows/ci.yml`, bloque explícito `permissions: contents: read` para limitar los privilegios del `GITHUB_TOKEN` al mínimo necesario.

### 📊 Monitoreo de Plataforma Windows y Auditoría Integral
- **Detalles Completos de Entorno Windows**:
  - Detección de edición de Windows, Build Number, UBR (Update Build Revision) y arquitectura (64-bit / ARM64) mediante consulta directa al Registro de Windows (`SOFTWARE\Microsoft\Windows NT\CurrentVersion`).
  - Exposición en `/api/system/status`, integración en el HUD superior y tabla de diagnóstico del sistema.
- **Resolución de Auditorías Técnicas (Claude N1-N9 & ChatGPT P0-P2)**:
  - Persistencia de `ignored_devices` en `core/config_mgr.py` para evitar que el hotplug de DirectShow reactive cámaras eliminadas.
  - Corrección de `SecretFilter` para soportar argumentos `%s` sin generar excepciones `TypeError`.
  - Tickets efímeros de preview de uso único (single-use) e invalidación por dispositivo con límite de capacidad estricto (cap a 100).
  - Documentación detallada en `docs/TROUBLESHOOTING.md` sobre contención de sockets en modo SRT Listener.
  - Incorporación de `CODE_OF_CONDUCT.md` bajo el estándar Contributor Covenant v2.1.
  - Eliminación absoluta de datos personales de contacto no profesionales en el 100% de los archivos.
  - Estandarización permanente de encabezados y descripciones funcionales en todos los módulos.
  - 98 pruebas unitarias y de integración pasando al 100% y 0 errores de linter.
