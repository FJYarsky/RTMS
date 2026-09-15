# Changelog — RTMS (Real-Time Multicam System) v2.2.0

Todas las modificaciones notables de este proyecto se documentan en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y el versionado sigue [Semantic Versioning](https://semver.org/lang/es/).

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

<!-- RTMS v2.2.0 Changelog -->
