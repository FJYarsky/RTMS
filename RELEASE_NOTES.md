# Notas Oficiales de Lanzamiento — RTMS

Historial completo y notas oficiales de lanzamiento organizadas cronológicamente para cada versión de RTMS.

---

## RTMS v2.6.0 — Previsualizaciones WebRTC WHEP, Canal WebSocket de Telemetría a 10 Hz, Monitoreo Determinista, Negociación MJPEG por Silicio y Escaneo Continuo Snyk
*(2026-09-23)*

### 🌐 Previsualizaciones WebRTC de Latencia Cero (<40 ms) con WHEP y Proxy Anti-CORS
- **Protocolo RFC 9397 (WHEP)**:
  - Integración nativa con MediaMTX WebRTC (`webrtc: yes`, `webrtcAddress: :8889`, `webrtcLocalUDPAddress: :8189`).
  - Visor HTML5 `<video id="preview-video">` en el frontend, eliminando la sobrecarga y latencia del streaming MJPEG en flujos activos.
  - Proxy seguro `POST /api/stream/{device_path}/whep` en FastAPI para evitar bloqueos CORS y mantener el tráfico dentro del mismo origen (`127.0.0.1:8000`).
  - Fallback automático y transparente al generador MJPEG para cámaras virtuales o flujos detenidos.

### ⚡ Canal WebSocket de Telemetría a 10 Hz y Eventos Reactivos
- **Ruta Asíncrona `/ws/telemetry`**:
  - `TelemetryWebSocketHub` con control de ciclo de vida: ticker de 10 Hz activo únicamente cuando hay clientes conectados (0% CPU en reposo).
  - Tasa de 10 Hz (100 ms) para métricas de video (FPS instantáneo, bitrate, dropped frames), GPU y rendimiento de red.
  - Muestreo a 1 Hz para métricas pesadas de sistema (CPU y memoria RAM).
  - Push reactivo inmediato de eventos de hardware y streaming (`device_lost`, `device_recovered`, `stream_started`, `stream_stopped`), eliminando la necesidad de polling HTTP continuo.
  - Mutación granular en tiempo real del DOM por identificador, sin re-renderizado destructivo.

### 📊 Monitoreo Determinista con `-progress pipe:1` (Sin Regex en Stderr)
- **Eliminación de Scraping Regex en Stderr**:
  - Inyección de `-progress pipe:1 -nostats` en el generador de comandos FFmpeg.
  - Lector asíncrono `proc.read_progress` en `StreamProc` para parseo determinista de pares `key=value` desde `stdout`.
  - Prevención garantizada de bloqueos de buffer de tubería (*pipe deadlock*) en Windows mediante drenado concurrente de `stdout` y `stderr`.
  - Contabilización precisa de fotogramas caídos (*dropped frames*) y total de frames procesados.

### 🔌 Negociación DirectShow MJPEG por Silicio en Webcams Físicas
- **Descompresión en el Chip Interno de la Cámara**:
  - Inyección de `-vcodec mjpeg` antes de la entrada DirectShow para dispositivos físicos.
  - Reducción de más del 95% del consumo de ancho de banda en el bus USB (de ~1000 Mbps en YUY2 sin comprimir a 25–40 Mbps en MJPEG).
  - Permite conectar 4 o más cámaras simultáneas en el mismo controlador o hub USB sin saturación de ancho de banda.

### 🛡️ Seguridad Continua con Snyk Security y Resolución de Dependabot
- **Escaneo Automatizado SAST & SCA**:
  - Workflow `.github/workflows/snyk.yml` para auditoría de vulnerabilidades con reporte SARIF integrado en GitHub Code Scanning.
  - Sincronización completa con `ruff >= 0.16.8` y `mypy >= 2.3.1` (absorbiendo y resolviendo Dependabot PR #13 y PR #14).
  - Resolución determinista de 68 dependencias con `uv.lock`.
  - `SECURITY.md` actualizado para soporte oficial de la versión `>= 2.6.0`.

### 📐 Modelos Pydantic v2 de Dominio Estricto
- **`core/config_models.py`**:
  - `CameraConfig`: validación estricta de resoluciones (`480p`, `720p`, `1080p`, `1440p`, `4K`), FPS (15–120), bitrate (500–50000 kbps), encoders y passphrases SRT (10–79 chars).
  - `SystemSettingsConfig`: validación de puertos MediaMTX (SRT, WebRTC) y ajustes del sistema.

### 🧪 Calidad, Verificación y Suite de Pruebas
- Suite ampliada con pruebas automatizadas completas cubriendo WebSockets, WHEP proxy, `-progress pipe:1`, modelos Pydantic v2 y workflows de CI/CD.
- Linters y formateador `ruff` validados sin advertencias.
- Preservación estricta del catálogo canónico de GitHub (32/32 [OK]).

---

## RTMS v2.5.2 — Optimización de Latencia Extrema en SRT/UDP, Soporte UDP Unicast/Multicast, Códigos QR Offline y Aceleración de Arranque
*(2026-09-22)*

### 🚀 Optimización de Latencia Extrema en SRT y UDP (VLC Media Player, OBS)
- **Modos UDP Unicast y Multicast**:
  - Soporte explícito para UDP Unicast (`udp_unicast`, por defecto a `127.0.0.1` o IP destino específica) para enlaces directos locales, y UDP Multicast (`udp_multicast`, grupo `239.255.0.X`) para distribución en red de área local (LAN).
  - Formato MRL canónico para VLC: `udp://@<ip>:<port>` sin parámetros de consulta query (`?pkt_size`), garantizando reconocimiento inmediato del analizador de red de VLC.
  - Comprobado en decodificación dummy en tiempo real de VLC con cero pérdida de paquetes y retardo inferior a 80 ms.
- **Reducción Drástica de Retardo en SRT**:
  - Eliminado `smoother=live` en publicaciones caller hacia MediaMTX, suprimiendo esperas de pacing innecesarias en tráfico de loopback local.
  - Fijación de GOP a 1 segundo (`gop = fps` en modo zerolatency), asegurando llegada continua de paquetes IDR/SPS/PPS para enganche de reproducción instantáneo (<100 ms).
  - Parámetros de multiplexión MPEG-TS optimizados: `-pat_period 0.1 -pcr_period 20` para sincronización ultrarrápida de reloj y demuxing.

### 📱 Códigos QR Offline para Conexión Móvil en VLC
- **Integración Autónoma sin Dependencias de Internet**:
  - Biblioteca `qrcode.min.js` empaquetada localmente (100% offline, sin llamadas externas a CDN).
  - Generación dinámica de código QR accesible con un clic desde las tarjetas de cámara y desde la vista de conexión universal OBS/VLC.
  - Permite a cámaras de control, directores de escena y operadores en smartphones/tablets apuntar la cámara de su dispositivo y abrir el stream al instante en VLC Mobile (iOS/Android).
  - Incluye botón de copiado directo al portapapeles y guía paso a paso de uso en VLC para móviles.

### ⚡ Arranque Instantáneo y Prevención de Diálogos UAC / Administrador
- **Desbloqueo Automático de Binarios Windows**:
  - Función `unblock_app_binaries` para eliminar flujos alternativos NTFS (`Zone.Identifier`) en `ffmpeg.exe`, `ffplay.exe` y `mediamtx.exe`.
- **Reglas Asíncronas de Firewall de Windows**:
  - Creación y verificación de reglas para `mediamtx.exe` ejecutadas en segundo plano (`asyncio.to_thread`) sin bloquear la apertura de la ventana de WebView2 (<1 segundo).
- **Temporizador Multimedia de Alta Precisión**:
  - Llamada a `timeBeginPeriod(1)` en Windows para asegurar resolución de reloj de 1 ms en el planificador de hilos, reduciendo el jitter de streaming.
- **Prioridad de Proceso para FFmpeg**:
  - Asignación de `ABOVE_NORMAL_PRIORITY_CLASS` (0x00008000) a los procesos de captura y codificación para evitar caídas de cuadros ante picos de uso del sistema.

### 👁️ Monitores de Vista Previa Instantáneos y Confiables
- **Inicialización de Latencia Cero**:
  - Parámetros `-probesize 100k -analyzeduration 500k -fflags nobuffer+flush_packets -flags low_delay` en flujos MJPEG y visores FFplay, abriendo la previsualización en menos de 200 ms.
  - Detección y generación virtual (`lavfi testsrc2`) para cámaras virtuales y estados inactivos, evitando excepciones en el demuxer DirectShow de Windows.

### 🎨 Refinamiento Estético y Consistencia Visual
- Corrección del diseño y estilos en el campo de entrada de puerto MediaMTX en el modal de Ajustes Generales (`form-ctrl`, fondo oscuro y borde unificado).
- Realineación geométrica del encabezado y badge de estado en el modal de vista previa.

---

## RTMS v2.5.1 — Compatibilidad de Reproducción SRT (VLC), Parches de Seguridad CodeQL y Sincronización en Memoria
*(2026-09-22)*

### 🎬 Compatibilidad Total de Reproducción SRT (VLC Media Player, ffplay, OBS)
- **Sintaxis Canónica RFC 3986**:
  - Inclusión de barra delimitadora (`/`) antes de los parámetros query en las URLs SRT generadas (`srt://IP:PORT/?streamid=read:{cam_id}`).
  - Resuelve la incompatibilidad en VLC 3.0 donde el parser de red descartaba el `streamid` al omitir la barra de ruta, impidiendo la reproducción.
- **Normalización de Latencia y Prevención de Retardo**:
  - Eliminado el parámetro `latency` de la URL cliente.
  - Corrige el problema de bloqueo/buffering de 2 minutos (120 s) provocado por la discrepancia de unidades (microsegundos en FFmpeg vs milisegundos en el módulo `access_srt` de VLC).
  - La latencia se negocia de forma óptima a nivel de servidor (120 ms por defecto).
- **Contraseña SRT Limpia por Defecto**:
  - Las cámaras recién añadidas o detectadas se configuran sin contraseña (`srt_passphrase: ""`), permitiendo la reproducción inmediata en clientes SRT estándar sin autenticación (`ERROR:BADSECRET`).
  - La protección criptográfica por contraseña se mantiene disponible de forma opcional mediante el modal de ajustes de cada cámara.

### 🛡️ Parches de Seguridad CodeQL (Alertas #11 y #12)
- **Alerta #11 (CWE-116 - Incomplete string escaping or encoding)**:
  - Corregido en `gui/static/app.js`: se reemplazó la concatenación insegura de JavaScript en atributos `onclick` por enlace declarativo `data-device-path="${escapeHtml(dev.device_path)}"` consumido de manera segura mediante `this.dataset.devicePath`.
- **Alerta #12 (CWE-312 - Clear-text storage of sensitive information)**:
  - Corregido en `core/mediamtx_mgr.py`: se eliminó el almacenamiento en texto claro de contraseñas SRT en el archivo `config/mediamtx.yml` en disco.
  - La configuración de rutas protegidas y contraseñas de lectura (`srtReadPassphrase`) se gestiona ahora exclusivamente en memoria a través de la API REST local de MediaMTX (`/v3/config/paths/add` y `/v3/config/paths/patch`).

### ⚡ Sincronización Dinámica de Rutas en MediaMTX
- Nuevos métodos asíncronos `sync_paths_api()` y `sync_path_api()` para actualización en caliente de credenciales y rutas en el Media Server.
- Sincronización automática invocada al iniciar MediaMTX, al actualizar o eliminar configuraciones de cámaras en la API REST y durante el ciclo de sincronización con hardware.

---

## RTMS v2.5.0 — Core Media Server, Pipeline Desacoplado, Blindaje de Kernel y Persistencia ACID
*(2026-09-22)*

### 🌐 Ingesta Desacoplada con MediaMTX (Opción A Estándar Broadcast)
- **Media Server Local (`bin/mediamtx.exe` v1.9.3)**:
  - FFmpeg publica localmente de forma ininterrumpida como caller (`srt://127.0.0.1:8890?streamid=publish:{cam_id}&mode=caller`).
  - MediaMTX expone el servicio en la red LAN a través de un puerto central SRT (por defecto `8890`, configurable en Ajustes en los rangos recomendados `8890-8990` o `9000-9200`).
  - Formato universal de conexión para OBS Studio y vMix:
    `srt://{ip}:{mediamtx_port}?streamid=read:{cam_id}&latency={latency}`.
  - **Inmunidad Total ante Desconexiones de Clientes**: Las aperturas, cierres o reconexiones de OBS Studio jamás detienen a FFmpeg ni causan reinicios de hardware ni parpadeos en las cámaras físicas.
  - Múltiples receptores pueden conectarse a la misma cámara simultáneamente sin sobrecargar la CPU del emisor.

### 🛡️ Blindaje de Procesos por Kernel (Win32 Job Objects)
- **Cero Procesos Huérfanos (`core/job_object.py`)**:
  - Implementación nativa con `kernel32.dll` del flag `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (0x2000).
  - Todas las instancias de FFmpeg, MediaMTX y visores FFplay quedan asociadas al Job Object de Windows.
  - Si RTMS es cerrado o finalizado desde el Administrador de Tareas, el kernel de Windows liquida atómica e instantáneamente todos los procesos secundarios.
- **Registro Centralizado de Tareas (`core/task_registry.py`)**:
  - Supervisión, drenaje y cancelación limpia de corrutinas asíncronas en el shutdown.

### 💾 Persistencia Transaccional ACID (SQLite WAL)
- **Capa de Repositorio (`core/repository/`)**:
  - Reemplazo de JSON monolítico por base de datos SQLite en modo `WAL` (`Write-Ahead Logging`) con `busy_timeout=5000` y transacciones inmediatas.
  - **Migración Automática Reversible**: Detección transparente de `config.json`, migración atómica a `config/rtms.db`, creación de copia de seguridad inmutable `config.json.v2.4.1.bak` y réplica exportada sincronizada.

### 🔄 Papelera y Recuperación de Cámaras Eliminadas (Bugfix Hallazgo #20)
- **Sección de Dispositivos Ocultados / Eliminados**:
  - Nuevos endpoints API: `GET /api/devices/ignored`, `POST /api/devices/unignore`, `POST /api/devices/unignore_all`.
  - Nueva sección colapsable en la interfaz Web con contador badge y botón interactivo `🔄 Restaurar Cámara` individual y masivo, devolviendo las cámaras a estado `STOPPED` con reasignación dinámica de puertos ante colisiones.

### 🧪 Calidad, CI/CD y Gobernanza GitHub
- Suite completa de 139 pruebas automatizadas (100% aprobadas).
- Tipado estricto `mypy` verificado en `core/` y `api/`.
- Linters y formato `ruff` validados sin advertencias.
- Catálogo canónico de GitHub preservado en 31/31 elementos raíz (`scripts/manage_descriptions.py --check`).
- Empaquetado portable con PyInstaller actualizado (`build_portable.bat`) con inclusión de `mediamtx.exe`, `mediamtx.example.yml` y soporte de `aiosqlite`.
- Avisos de licencias de terceros actualizados con la licencia MIT de MediaMTX (`THIRD_PARTY_NOTICES.md`).

---

## RTMS v2.4.1 — Corrección de Detección de Dispositivos, Desconexión Hotplug y Control de Inicio
*(2026-09-22)*

### 🎥 Corrección Forense de Detección DirectShow (Micrófonos vs Video)
- **Aislamiento Estricto de Cámaras de Video (`core/hardware.py`)**:
  - Detección precisa de salida moderna de FFmpeg 7.x+ mediante marcadores `(video)`, `(audio)`, `(none)` y corchetes `[in#`.
  - Eliminado por completo el falso positivo reportado al desactivar la cámara de la laptop con la tecla rápida F5 o interruptor físico: en lugar de caer al parser heredado y capturar erróneamente los micrófonos del sistema, el sistema identifica correctamente 0 dispositivos de video y retorna `[]`.
  - Filtro canónico por GUIDs de DirectShow: exclusión automática e incondicional de dispositivos bajo la categoría `KSCATEGORY_AUDIO` (`33D9A762-90C8-11D0-BD43-00A0C911CE86` / `4DF0A701-02CD-11CF-8356-0080C73DF13A`) y rutas DirectShow con prefijo `@device_cm_`.

### 🔌 Manejo Reactivo de Desconexión Física (Hotplug)
- **Transición Inmediata a `DISCONNECTED` (`core/stream_manager.py`)**:
  - Al desenchufar una cámara USB o apagarla por hardware, los errores `ErrorCategory.DEVICE` son interceptados al instante. El proceso de FFmpeg se detiene ordenadamente, pasando el stream a `State.DISCONNECTED` sin penalizar contadores de error de software ni entrar en ciclos de reintentos innecesarios con backoff.
  - **Detección de Congelamiento a 0 FPS**: Watchdog optimizado que detecta streams activos sin entrega de cuadros por más de 8 segundos continuos. Si el hardware desapareció de DirectShow, se detiene el proceso y se marca `DISCONNECTED`.
  - **Reconexión Automática Limpia**: Al volver a enchufar la cámara o reactivarla por teclado, el sistema limpia estados de falla anteriores y, si la cámara posee `auto_start = True`, reanuda la transmisión automáticamente en menos de 5 segundos.
  - **Sondeo Acelerado**: Intervalo de sondeo periódico de hardware reducido a 5 segundos (anteriormente 20 segundos).

### ⚙️ Control de Inicio y Política de Carga Inicial
- **Desactivación de Transmisión Masiva al Iniciar (`core/config_mgr.py`)**:
  - Las cámaras recién descubiertas en el sistema se registran con `auto_start = False` por defecto. Al iniciar RTMS por primera vez, las cámaras permanecen en reposo (`STOPPED`), permitiendo al usuario decidir individualmente cuáles iniciar o activar para inicio automático.
  - Plantillas de configuración por defecto actualizadas con `unattended_autostart: false`.

### 🧹 Limpieza de Ramas y Catálogo GitHub Oficial
- Eliminación de branches y worktrees temporales huérfanos. Rama `main` establecida como única rama activa.
- Catálogo oficial de 31 elementos raíz verificado y sincronizado al 100%.

---

## RTMS v2.4.0 — Arquitectura Limpia, Descomposición Modular sin Fachadas, Tooling Determinista y Cierre de Fase 1
*(2026-09-22)*

### 🏗️ Arquitectura Limpia y Descomposición Modular
- **Eliminación Total de Monolitos**:
  - `core/ffmpeg_mgr.py` (813 líneas) descompuesto y reemplazado en su totalidad por 4 módulos de responsabilidad única: `stream_proc.py`, `command_builder.py`, `hardware_sync.py` y `stream_manager.py`.
  - `api/routes.py` (797 líneas) descompuesto y transformado en el paquete canónico de FastAPI `api/routes/` (`health.py`, `streams.py`, `preview.py`, `config.py`, `system.py`, `power.py`) y `api/deps.py`.
- **Cero Fachadas Residuales**: Prescindido de intermediarios y aliases artificiales. Los módulos se resuelven directamente sin capas superfluas ni wrappers.

### 🛡️ Erradicación Total de "Mock Drift" en Tests
- Actualización integral de la suite de pruebas automatizadas: cada test importa y mockea directamente el módulo real donde se ejecuta la lógica (`core.stream_proc`, `core.stream_manager`, `api.routes.preview`, `api.routes.streams`, `api.deps`), eliminando cualquier falso positivo.

### 📦 Tooling Determinista y Catálogo Oficial
- **`justfile`**: Recetas estándar de automatización de desarrollo (`install`, `test`, `lint`, `format`, `build`).
- **`.pre-commit-config.yaml`**: Hooks locales para validación de linters y formato con Ruff.
- **`uv.lock`**: Resolución determinista de dependencias del proyecto.
- **Catálogo Canónico GitHub**: Dimensionamiento y preservación estricta de 31 elementos raíz oficiales sin truncamiento ni drift.

---

## RTMS v2.3.0 — Seguridad Crítica, Gobernador Energético Win32 y Estandarización de Arquitectura
*(2026-09-19)*

### 🛡️ Seguridad Crítica y Protección de Sesión (Hotfixes P0)
- **Corrección de Limpieza Asíncrona de Procesos (`core/process_cleanup.py`)**:
  - Resuelto fallo P0-01 encapsulando `asyncio.gather` dentro de una corrutina real antes de llamar a `asyncio.run_coroutine_threadsafe()`, garantizando la terminación ordenada de los managers de streaming y preview sin excepciones de runtime.
- **Filtro Estricto y Seguro de Terminación de Procesos (`core/process_cleanup.py`)**:
  - Resuelto fallo P0-02 acotando la terminación forzada exclusivamente a subprocesos hijos de RTMS (`ppid == my_pid`), binarios ubicados en el directorio `bin/` de RTMS o líneas de comando con marca `rtms`. Protege instancias externas de FFmpeg utilizadas por otras aplicaciones en el sistema del usuario.
- **Eliminación de Fuga de Tokens en Query Parameters (`api/routes.py`)**:
  - Resuelto fallo P0-03 eliminando la aceptación de tokens en la URL (`?token=...`), retornando código HTTP 403. Incorporadas cabeceras `Cache-Control: no-store, no-cache, must-revalidate` y `Pragma: no-cache` en `/api/stream/{device}/connect_url`.
- **Autenticación por Cookie HttpOnly y Eliminación de Meta Tag (`main.py` y `gui/templates/index.html`)**:
  - Resuelto fallo P0-04 eliminando `<meta name="rtms-token">` del DOM y del contexto de plantilla. Emisión de cookie segura `rtms_session` con flags `httponly=True, samesite='lax'` y configuración de `credentials: 'same-origin'` en todas las peticiones `apiFetch` de la interfaz web.
- **Corrección de Visualización y Revelado de Contraseña en URLs (`gui/static/app.js`)**:
  - Las URLs de conexión mostradas en las tarjetas cargan inmediatamente la contraseña descifrada para streams activos e incorporan un botón conmutable para ocultar/mostrar la clave (icono 👁️ / 🔒), garantizando la copia exacta al portapapeles.

### ⚡ Gestión Energética Profesional y Nativa (Win32)
- **Nuevo Módulo de Energía Nativo (`core/power_mgr.py`)**:
  - Implementación de control energético mediante APIs Win32 nativas (`powrprof.dll`, `kernel32.dll`) sin invocar scripts externos de PowerShell, eliminando alertas de antivirus y falsos positivos.
- **Gobernador Dinámico de Energía (`DynamicPowerGovernor`)**:
  - Elevación automática al plan de energía de **Alto Rendimiento** de Windows en cuanto inicia al menos una transmisión activa (`active_streams >= 1`) y restauración inmediata y transparente del plan original al concluir todas las transmisiones (`active_streams == 0`).
- **Prevención Nativa de Suspensión de Pantalla y Equipo**:
  - Activación continua de `SetThreadExecutionState` (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED`) durante la operación activa.
- **Optimización de Adaptadores de Red Vía Registro**:
  - Desactivación de ahorro de energía (`PnPCapabilities = 24`) mediante manipulación directa en el registro con `winreg` y verificación de privilegios `is_admin()`.
- **Rollback Atómico y Persistencia**:
  - Creación de respaldo seguro en `config/power_backup.json` con restauración garantizada de directivas originales al cerrar o solicitar la restauración.

### 🔄 Ruptura Limpia de Retrocompatibilidad (< 2.3.0)
- **Esquema de Configuración v4 (`core/config_mgr.py`)**:
  - Actualizado a `CURRENT_SCHEMA_VERSION = 4` y purgadas todas las rutinas de migración heredadas v1 y v2.
  - Detección automática de versiones de configuración previas (< 4) con respaldo seguro en `config/config.json.legacy_v2_bak` y reinicialización limpia a valores por defecto para v2.3.0.
  - Eliminado el script obsoleto `run_silent.vbs` y actualizadas las referencias de arranque en el proyecto.

### 🛠️ Estandarización de Arquitectura y Herramientas (PEP 621)
- **Modernización de pyproject.toml**:
  - Configuración del sistema de empaquetado estándar `hatchling` con metadatos PEP 621.
  - Incorporadas reglas de linting y formato estrictas con Ruff (`line-length = 120`, reglas `E`, `F`, `W`, `I`, `B`), tipado con Mypy y configuración de Pytest.
  - 100% de la base de código formateada y alineada con estándares modernos de Python.

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
  - 5 tests de integración en vivo añadidos a la suite oficial de Pytest, elevando la cobertura a 113 tests unitarios y de integración pasando al 100%.

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
