# Catálogo de Propuestas de Cambio (RFCs)

Este catálogo documenta las propuestas técnicas de cambio y especificaciones formales de ingeniería (*Requests for Comments*) de RTMS. Cada RFC detalla la arquitectura de bajo nivel, flujos de datos, modelos de memoria, planes de pruebas y estrategias de despliegue sin interrupción de servicio.

---

## 📊 Matriz de RFCs

| RFC | Título de la Propuesta | Estado | Módulos Clave | Resumen Ejecutivo |
| :--- | :--- | :--- | :--- | :--- |
| **[[RFC-0001\|RFC-0001-Protocolo-Verificacion-E2e-y-Benchmark-Optico]]** | Protocolo de Verificación E2E y Benchmark Óptico | `Implemented` | `core/pipeline_verifier.py`, `core/optical_clock.py` | Generación de reloj visual binario de 64 bits a 30/60 FPS con muestreo por centroides de píxel para auditar latencia con precisión de 1 ms. |
| **[[RFC-0002\|RFC-0002-Arquitectura-Distribucion-Multicam-Baja-Latencia]]** | Arquitectura de Distribución Multicámara <100 ms | `Implemented` | `core/stream_manager.py`, `core/command_builder.py` | Ingesta desacoplada mediante workers FFmpeg con control de tasa CBR/VBV estricto y retransmisión 1-a-N a través de MediaMTX. |
| **[[RFC-0003\|RFC-0003-Persistencia-Transaccional-Sqlite-Wal-Migrador]]** | Persistencia Transaccional SQLite WAL y Migrador | `Implemented` | `core/repository/database.py`, `core/repository/migrator.py` | Migración idempotente de `config.json` a esquema relacional normalizado con durabilidad WAL y respaldo inmutable `.bak`. |
| **[[RFC-0004\|RFC-0004-Pipeline-Previsualizacion-Zero-Copy-Tickets-Efimeros]]** | Pipeline de Previsualización Zero-Copy y Tickets | `Implemented` | `core/preview_mgr.py`, `api/deps.py`, `api/routes/preview.py` | Transmisión on-demand de vistas previas `multipart/x-mixed-replace` delimitadas por marcadores JPEG SOI/EOI y tickets efímeros single-use. |
| **[[RFC-0005\|RFC-0005-Blindaje-Procesos-Kernel-Win32-Ciclo-Vida-Resiliente]]** | Blindaje de Procesos Kernel Win32 y Ciclo de Vida | `Implemented` | `core/job_object.py`, `core/task_registry.py` | Encapsulado de subprocesos en Win32 Job Objects con terminación forzada atómica en caídas del SO y drenaje ordenado en shutdown. |
| **[[RFC-0006\|RFC-0006-Aislamiento-Subprocesos-P-Cores-y-Control-Optico-Uvc]]** | Aislamiento P-Cores y Control Óptico DirectShow UVC | `Implemented` | `core/process_optimizer.py`, `core/uvc_control.py` | Pinning de FFmpeg/MediaMTX en P-Cores (`GetLogicalProcessorInformationEx`), `HIGH_PRIORITY_CLASS` y bloqueo de obturador UVC <=1/60s para asegurar 60 FPS estables. |

---

## 🔍 Navegación Directa a Propuestas Técnicas

* [[RFC-0001: Verificación E2E de Latencia y Reloj Óptico|RFC-0001-Protocolo-Verificacion-E2e-y-Benchmark-Optico]]
* [[RFC-0002: Arquitectura Multicámara de Baja Latencia|RFC-0002-Arquitectura-Distribucion-Multicam-Baja-Latencia]]
* [[RFC-0003: Persistencia Transaccional SQLite WAL y Migraciones|RFC-0003-Persistencia-Transaccional-Sqlite-Wal-Migrador]]
* [[RFC-0004: Pipeline de Previsualización y Tickets Efímeros|RFC-0004-Pipeline-Previsualizacion-Zero-Copy-Tickets-Efimeros]]
* [[RFC-0005: Blindaje de Procesos en Kernel y Ciclo de Vida Resiliente|RFC-0005-Blindaje-Procesos-Kernel-Win32-Ciclo-Vida-Resiliente]]
* [[RFC-0006: Aislamiento P-Cores y Control Óptico UVC|RFC-0006-Aislamiento-Subprocesos-P-Cores-y-Control-Optico-Uvc]]
