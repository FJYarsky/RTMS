# Matriz de Trazabilidad Arquitectónica y Documental (Traceability Matrix)

* **Versión del Sistema**: RTMS v2.8.0+
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Gobernanza de Arquitectura / QA / Mantenibilidad a Largo Plazo

---

## 1. Mapeo Módulo a Decisiones de Arquitectura (ADRs) y Especificaciones (RFCs)

Esta matriz establece el vínculo bidireccional formal entre cada archivo y módulo del código fuente de RTMS, sus registros de decisión arquitectónica (ADRs), especificaciones de cambio (RFCs) y la suite de pruebas automatizadas que certifica su cumplimiento.

| Módulo / Archivo de Código Fuente | Capa / Subsistema | ADRs Vinculados | RFCs Vinculados | Tests Automatizados de Validación |
| :--- | :--- | :---: | :---: | :--- |
| ``main.py`` | Punto de Entrada & Ciclo de Vida | `ADR-0012`, `ADR-0013`, `ADR-0018`, `ADR-0019` | `RFC-0005` | `test_audit_lifecycle.py`, `test_fastapi_headless.py`, `test_single_instance.py` |
| ``core/stream_manager.py`` | Orquestación & FSM Watchdog | `ADR-0007`, `ADR-0009`, `ADR-0017` | `RFC-0002` | `test_stream_lifecycle.py`, `test_stream_resilience.py`, `test_stress_concurrency.py` |
| ``core/stream_proc.py`` | Proceso de Streaming & URLs | `ADR-0003`, `ADR-0005`, `ADR-0017` | `RFC-0002` | `test_command_builder.py`, `test_vlc_integration.py` |
| ``core/command_builder.py`` | Generador de Flags FFmpeg | `ADR-0002`, `ADR-0003`, `ADR-0007` | `RFC-0002` | `test_command_builder.py`, `test_ffmpeg_live.py` |
| ``core/hardware.py`` | Detección DirectShow & Silicio | `ADR-0002`, `ADR-0007`, `ADR-0014` | `RFC-0002` | `test_hardware_parser.py`, `test_hardware_concurrency.py` |
| ``core/job_object.py`` | Kernel Win32 Job Objects | `ADR-0009` | `RFC-0005` | `test_audit_new_features.py` |
| ``core/repository/database.py`` | Motor SQLite WAL Transaccional | `ADR-0010` | `RFC-0003` | `test_config_persistence.py`, `test_config_isolation.py` |
| ``core/repository/config_repository.py`` | Patrón Repositorio de Datos | `ADR-0010` | `RFC-0003` | `test_config_mgr.py`, `test_config_persistence.py` |
| ``core/repository/migrator.py`` | Migrador JSON a SQLite WAL | `ADR-0010` | `RFC-0003` | `test_config_isolation.py` |
| ``core/secrets_mgr.py`` | Criptografía en Reposo (DPAPI) | `ADR-0003`, `ADR-0011` | `RFC-0003` | `test_secrets_mgr.py`, `test_audit_security.py` |
| ``core/power_mgr.py`` | Gestión de Energía & Red Win32 | `ADR-0012` | `RFC-0005` | `test_power_mgr.py` |
| ``core/system_env.py`` | Reloj 1ms & Reglas de Firewall | `ADR-0012` | `RFC-0005` | `test_audit_v260_features.py` |
| ``core/single_instance.py`` | Named Mutex Win32 | `ADR-0013` | `RFC-0005` | `test_single_instance.py` |
| ``core/preview_mgr.py`` | Admisión Concurrente de Vistas | `ADR-0016` | `RFC-0004` | `test_preview.py`, `test_audit_preview.py` |
| ``core/telemetry_hub.py`` | WebSocket Ticker a 10 Hz | `ADR-0015` | `RFC-0001` | `test_telemetry.py` |
| ``core/telemetry.py`` | Monitores Host (GPU / Red) | `ADR-0015` | `RFC-0001` | `test_telemetry.py` |
| ``core/task_registry.py`` | Registro & Drenaje de Tareas | `ADR-0009` | `RFC-0005` | `test_audit_lifecycle.py` |
| ``core/process_cleanup.py`` | Rutina de Liquidación Final | `ADR-0009` | `RFC-0005` | `test_audit_lifecycle.py` |
| ``core/port_mgr.py`` | Asignación Dinámica de Sockets | `ADR-0005`, `ADR-0017` | `RFC-0002` | `test_port_mgr.py` |
| ``core/pipeline_verifier.py`` | Verificador E2E & Ping Óptico | `ADR-0004` | `RFC-0001` | `test_e2e_complete_pipeline.py`, `test_ultra_low_latency_pipeline.py` |
| ``core/latency_bench.py`` | Benchmark Sintético de Latencia | `ADR-0004` | `RFC-0001` | `test_latency_benchmark.py` |
| ``core/sanitizer.py`` | Sanitización de Logs & URLs | `ADR-0008` | `RFC-0001` | `test_sanitizer.py`, `test_sanitizer_extra.py` |
| ``core/tray_icon.py`` | Bandeja del Sistema (pystray) | `ADR-0019` | `RFC-0005` | `test_tray.py` |
| ``api/deps.py`` | Auth Token & Tickets Efímeros | `ADR-0018` | `RFC-0004` | `test_audit_security.py`, `test_audit_preview.py` |
| ``api/schemas.py`` | Validación Pydantic | `ADR-0003`, `ADR-0018` | `RFC-0003` | `test_schemas.py` |
| ``api/routes/streams.py`` | Endpoints de Transmisión | `ADR-0001`, `ADR-0017` | `RFC-0002` | `test_stream_lifecycle.py` |
| ``api/routes/preview.py`` | Endpoints de Previsualización | `ADR-0016` | `RFC-0004` | `test_audit_preview.py` |
| ``api/routes/ws.py`` | Endpoint WebSocket Telemetría | `ADR-0015` | `RFC-0001` | `test_telemetry.py` |
| ``gui/static/app.js`` | Lógica Frontend & HUD | `ADR-0015`, `ADR-0019` | `RFC-0004` | `test_gui_visual.py` |

---

## 2. Gobernanza de Mantenimiento y Ciclo de Vida Documental

1. **Inmutabilidad y Versionado**: Los ADRs una vez aceptados son registros históricos inmutables. Toda evolución o modificación de diseño debe reflejarse mediante un nuevo ADR con relación explícita `Reemplazado por [ADR-XXXX]`.
2. **Proceso Obligatorio de RFC**: Cualquier cambio que modifique firmas de la API REST, esquemas de bases de datos o parámetros de protocolo de red requiere un RFC en estado `Approved` antes de fusionar el código fuente a la rama principal.
3. **Validación Automatizada de Conformidad**: El test continuo `tests/test_adr_rfc_standards.py` se ejecuta en cada ejecución de CI/CD para verificar la integridad sintáctica y la presencia en los índices de todos los ADRs y RFCs.
