# Catálogo de Registros de Decisiones de Arquitectura (ADR)

Este directorio documenta de manera formal, histórica e inmutable todas las decisiones arquitectónicas fundamentales que rigen el diseño, desarrollo, protocolos y funcionamiento del núcleo de **RTMS (Real-Time Multicam System)**.

Seguimos el estándar unificado de Michael Nygard para Architecture Decision Records (ADRs).

---

## Ciclo de Vida de un ADR
* **Propuesto**: Decisión en evaluación técnica o fase de RFC.
* **Aceptado**: Decisión aprobada, implementada y con cobertura de pruebas en el núcleo.
* **Reemplazado**: La decisión ha sido sustituida por un ADR posterior más moderno.
* **Obsoleto**: La funcionalidad o tecnología ha sido retirada de la base de código.

---

## Índice Oficial de ADRs

| ID | Título de la Decisión | Estado | Fecha | Área |
| :--- | :--- | :---: | :---: | :--- |
| [**ADR-0001**](0001-adopcion-mediamtx-broker-central.md) | Adopción de MediaMTX como Broker Central y Servidor de Streaming | **Aceptado** | 2026-09-15 | Core / Red |
| [**ADR-0002**](0002-negociacion-dinamica-formatos-directshow.md) | Negociación Dinámica de Formatos DirectShow y Sondeo de Pines MJPEG | **Aceptado** | 2026-09-30 | Hardware / Core |
| [**ADR-0003**](0003-cifrado-simetrico-passphrase-srt.md) | Cifrado Simétrico AES-128 con Passphrase y Autenticación en SRT | **Aceptado** | 2026-09-20 | Seguridad / Red |
| [**ADR-0004**](0004-verificador-ineludible-reloj-optico-ping.md) | Verificador Ineludible E2E y Medición Matemática de Ping Óptico | **Aceptado** | 2026-09-30 | QA / Telemetría |
| [**ADR-0005**](0005-distribucion-udp-multicast-unicast.md) | Distribución UDP Multicast (239.255.0.x) y Unicast de Baja Latencia | **Aceptado** | 2026-09-18 | Red / Streaming |
| [**ADR-0006**](0006-desacoplamiento-asincrono-fastapi-system-tray.md) | Desacoplamiento de FastAPI Asíncrono, GUI Web y System Tray Nativo | **Reemplazado** | 2026-09-16 | GUI / Core |
| [**ADR-0007**](0007-priorizacion-codificadores-hardware.md) | Detección y Priorización de Codificadores GPU con Fallback Resiliente | **Aceptado** | 2026-09-17 | Hardware / Video |
| [**ADR-0008**](0008-sanitizacion-datos-sensibles-y-descripciones-canonicas.md) | Sanitización Retroactiva de PII y Descripciones Canónicas de GitHub | **Aceptado** | 2026-09-29 | Seguridad / Repositorio |
| [**ADR-0009**](0009-blindaje-kernel-win32-job-objects.md) | Blindaje de Subprocesos con Windows Job Objects y Supresión de Procesos Huérfanos | **Aceptado** | 2026-10-01 | Core / Kernel / Concurrencia |
| [**ADR-0010**](0010-persistencia-transaccional-sqlite-wal-migraciones.md) | Persistencia Transaccional ACID en SQLite WAL y Migraciones Idempotentes | **Aceptado** | 2026-10-01 | Core / Base de Datos |
| [**ADR-0011**](0011-cifrado-reposo-credenciales-windows-dpapi.md) | Cifrado en Reposo de Secretos y Passphrases mediante Windows DPAPI | **Aceptado** | 2026-10-01 | Seguridad / Criptografía |
| [**ADR-0012**](0012-prevencion-suspension-optimizacion-red-reloj-1ms.md) | Prevención de Suspensión, Optimización Energética de Red y Calibración de Reloj de 1 ms | **Aceptado** | 2026-10-01 | OS / Rendimiento / Red |
| [**ADR-0013**](0013-control-instancia-unica-win32-named-mutex.md) | Aislamiento de Instancia Única mediante Win32 Named Mutex Global/Local Jerárquico | **Aceptado** | 2026-10-01 | Core / IPC / Win32 |
| [**ADR-0014**](0014-coalescencia-single-flight-cache-ttl-hardware.md) | Coalescencia Single-Flight y Caché TTL en Sondeo de Hardware DirectShow | **Aceptado** | 2026-10-01 | Hardware / Concurrencia |
| [**ADR-0015**](0015-hub-reactivo-telemetria-10hz-bajo-demanda.md) | Hub Reactivo de Telemetría a 10 Hz con Suscripción Bajo Demanda y Doble Cadencia | **Aceptado** | 2026-10-01 | Telemetría / WebSockets |
| [**ADR-0016**](0016-control-admision-previsualizacion-mjpeg-on-demand.md) | Control de Admisión Concurrente y Streaming de Previsualización On-Demand | **Aceptado** | 2026-10-01 | Video / Memoria / HTTP |
| [**ADR-0017**](0017-taxonomia-errores-maquina-estados-watchdog-backoff.md) | Taxonomía Formal de Errores, Máquina de Estados Finita y Watchdog con Backoff Exponencial | **Aceptado** | 2026-10-01 | Core / Resiliencia / FSM |
| [**ADR-0018**](0018-seguridad-api-token-tickets-efimeros-proactor.md) | Blindaje de Seguridad en API Local, Tokens de Sesión y Mitigación Proactor | **Aceptado** | 2026-10-01 | Seguridad / API / Red |
| [**ADR-0019**](0019-interfaz-nativa-escritorio-webview2-bandeja-sistema.md) | Interfaz Nativa de Escritorio con WebView2 (pywebview) y Persistencia al System Tray | **Aceptado** | 2026-10-01 | GUI / Escritorio / Concurrencia |
| [**ADR-0020**](0020-afinidad-procesos-p-cores-arquitecturas-hibridas-windows.md) | Afinidad de Procesos a P-Cores en Arquitecturas Híbridas de Windows y Prioridad de Tiempo Real Suave | **Aceptado** | 2026-10-03 | OS / Rendimiento / Concurrencia |
| [**ADR-0021**](0021-control-directshow-com-uvc-bloqueo-auto-exposicion.md) | Control DirectShow COM UVC y Bloqueo de Auto-Exposición para Prevención de Caídas de FPS | **Aceptado** | 2026-10-03 | Hardware / Video / DirectShow |
| [**ADR-0022**](0022-ciclo-vida-lazy-apagado-suave-mediamtx.md) | Ciclo de Vida Lazy y Apagado Suave con Período de Gracia para MediaMTX | **Aceptado** | 2026-10-03 | Core / Recursos / Ciclo de Vida |
| [**ADR-0023**](0023-canonicidad-udp-unicast-desmitificacion-srt.md) | Canonicidad de UDP Unicast y Desmitificación de SRT como Protocolo Predeterminado | **Aceptado** | 2026-10-03 | Red / Protocolos / Streaming |
| [**ADR-0024**](0024-preservacion-aspect-ratio-mitigacion-bufferbloat-vbv.md) | Preservación de Relación de Aspecto y Mitigación de Bufferbloat VBV a Nivel de Cuadro | **Aceptado** | 2026-10-03 | Video / FFmpeg / Hardware |

---

## Cómo Proponer un Nuevo ADR
1. Copia la plantilla base desde [`docs/adr/template.md`](template.md).
2. Asigna el número consecutivo siguiente (`0025-...md`).
3. Describe el contexto, las alternativas evaluadas y las consecuencias esperadas.
4. Si la decisión amerita cambios profundos de protocolo o arquitectura de datos, acompaña el ADR con una propuesta en [`docs/rfc/`](../rfc/).
