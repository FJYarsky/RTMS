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
| [**ADR-0001**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0001-adopcion-mediamtx-broker-central.md) | Adopción de MediaMTX como Broker Central y Servidor de Streaming | **Aceptado** | 2026-09-15 | Core / Red |
| [**ADR-0002**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0002-negociacion-dinamica-formatos-directshow.md) | Negociación Dinámica de Formatos DirectShow y Sondeo de Pines MJPEG | **Aceptado** | 2026-09-30 | Hardware / Core |
| [**ADR-0003**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0003-cifrado-simetrico-passphrase-srt.md) | Cifrado Simétrico AES-128 con Passphrase y Autenticación en SRT | **Aceptado** | 2026-09-20 | Seguridad / Red |
| [**ADR-0004**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0004-verificador-ineludible-reloj-optico-ping.md) | Verificador Ineludible E2E y Medición Matemática de Ping Óptico | **Aceptado** | 2026-09-30 | QA / Telemetría |
| [**ADR-0005**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0005-distribucion-udp-multicast-unicast.md) | Distribución UDP Multicast (239.255.0.x) y Unicast de Baja Latencia | **Aceptado** | 2026-09-18 | Red / Streaming |
| [**ADR-0006**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0006-desacoplamiento-asincrono-fastapi-system-tray.md) | Desacoplamiento de FastAPI Asíncrono, GUI Web y System Tray Nativo | **Aceptado** | 2026-09-16 | GUI / Core |
| [**ADR-0007**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0007-priorizacion-codificadores-hardware.md) | Detección y Priorización de Codificadores GPU con Fallback Resiliente | **Aceptado** | 2026-09-17 | Hardware / Video |
| [**ADR-0008**](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/0008-sanitizacion-datos-sensibles-y-descripciones-canonicas.md) | Sanitización Retroactiva de PII y Descripciones Canónicas de GitHub | **Aceptado** | 2026-09-29 | Seguridad / Repositorio |

---

## Cómo Proponer un Nuevo ADR
1. Copia la plantilla base desde [`docs/adr/template.md`](file:///C:/Users/joaqu/Desktop/RTMS/docs/adr/template.md).
2. Asigna el número consecutivo siguiente (`0009-...md`).
3. Describe el contexto, las alternativas evaluadas y las consecuencias esperadas.
4. Si la decisión amerita cambios profundos de protocolo o arquitectura de datos, acompaña el ADR con una propuesta en [`docs/rfc/`](file:///C:/Users/joaqu/Desktop/RTMS/docs/rfc/).
