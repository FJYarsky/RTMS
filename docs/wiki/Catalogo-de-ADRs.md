# Catálogo de Registros de Decisión Arquitectónica (ADRs)

Este catálogo documenta las **19 decisiones técnicas formales** que gobiernan la arquitectura, seguridad, concurrencia y persistencia de RTMS. Cada ADR sigue el estándar de ingeniería MADR (Markdown Architectural Decision Records).

---

## 📊 Matriz Resumen de Decisiones

| ID | Título de la Decisión | Estado | Subsistema Impactado | Decisión Clave |
| :--- | :--- | :--- | :--- | :--- |
| **[[ADR-0001\|ADR-0001-Adopcion-Mediamtx-Broker-Central]]** | Adopción de MediaMTX como Broker Central | `Accepted` | Red & Ingesta | Uso de broker Go mono-binario para multiplexión 1-a-N sin duplicar transcodificación. |
| **[[ADR-0002\|ADR-0002-Negociacion-Dinamica-Formatos-Directshow]]** | Negociación Dinámica de Formatos DirectShow | `Accepted` | Captura USB | Priorización de entrada MJPEG sobre RAW para reducir uso del bus USB 2.0/3.0. |
| **[[ADR-0003\|ADR-0003-Cifrado-Simetrico-Passphrase-Srt]]** | Cifrado Simétrico Passphrase SRT | `Accepted` | Seguridad en Red | Cifrado AES-128 nativo en sockets SRT sin degradación de latencia. |
| **[[ADR-0004\|ADR-0004-Verificador-Ineludible-Reloj-Optico-Ping]]** | Verificador Ineludible por Reloj Óptico | `Accepted` | Verificación E2E | Código de barras óptico binario de 64 bits para auditar latencia con precisión de 1 ms. |
| **[[ADR-0005\|ADR-0005-Distribucion-Udp-Multicast-Unicast]]** | Distribución UDP Multicast LAN | `Accepted` | Red Local | Mapeo determinista en rango 239.255.0.x y paquetes MTU de 1316 bytes. |
| **[[ADR-0006\|ADR-0006-Desacoplamiento-Asincrono-Fastapi-System-Tray]]** | Desacoplamiento FastAPI y System Tray | `Accepted` | Concurrencia | Ejecución de FastAPI y WebView2 en hilos separados sincronizados vía callbacks thread-safe. |
| **[[ADR-0007\|ADR-0007-Priorizacion-Codificadores-Hardware]]** | Priorización de Encoders por Hardware | `Accepted` | Codificación | Detección única en arranque: NVENC > QSV > AMF > CPU libx264. |
| **[[ADR-0008\|ADR-0008-Sanitizacion-Datos-Sensibles-y-Descripciones-Canonicas]]** | Sanitización y Descripciones Canónicas | `Accepted` | Gobernanza Git | Catálogo inmutable de 32 elementos raíz con longitud estricta <45 caracteres. |
| **[[ADR-0009\|ADR-0009-Blindaje-Kernel-Win32-Job-Objects]]** | Blindaje Kernel con Win32 Job Objects | `Accepted` | Ciclo de Vida | Flag `KILL_ON_JOB_CLOSE` para erradicación determinista de procesos zombies en caídas. |
| **[[ADR-0010\|ADR-0010-Persistencia-Transaccional-Sqlite-Wal-Migraciones]]** | Persistencia Transaccional SQLite WAL | `Accepted` | Almacenamiento | Migración de `config.json` a `rtms.db` bajo WAL con respaldo inmutable previo. |
| **[[ADR-0011\|ADR-0011-Cifrado-Reposo-Credenciales-Windows-Dpapi]]** | Cifrado en Reposo con Windows DPAPI | `Accepted` | Seguridad Local | Cifrado de passphrases en reposo usando `CryptProtectData` ligado a la cuenta del SO. |
| **[[ADR-0012\|ADR-0012-Prevencion-Suspension-Optimizacion-Red-Reloj-1ms]]** | Prevención de Suspensión y Reloj 1 ms | `Accepted` | Kernel & SO | `SetThreadExecutionState`, `timeBeginPeriod(1)` y `PnPCapabilities = 24`. |
| **[[ADR-0013\|ADR-0013-Control-Instancia-Unica-Win32-Named-Mutex]]** | Control de Instancia Única Named Mutex | `Accepted` | Sistema Operativo | Mutex `Global\RTMS_SingleInstance_Mutex` para evitar colisiones de puertos y hardware. |
| **[[ADR-0014\|ADR-0014-Coalescencia-Single-Flight-Cache-Ttl-Hardware]]** | Coalescencia Single-Flight DirectShow | `Accepted` | Hardware USB | Caché con TTL de 4 segundos y suscripción concurrente para evitar ráfagas en USB. |
| **[[ADR-0015\|ADR-0015-Hub-Reactivo-Telemetria-10hz-Bajo-Demanda]]** | Hub Reactivo de Telemetría a 10 Hz | `Accepted` | WebSockets | Ticker asíncrono que solo consume CPU cuando hay al menos 1 suscriptor WebSocket conectado. |
| **[[ADR-0016\|ADR-0016-Control-Admision-Previsualizacion-Mjpeg-On-Demand]]** | Control de Admisión MJPEG On-Demand | `Accepted` | Multimedia | Semáforo de admisión (máx 3 slots) y extractor de cuadros binario SOI/EOI con tope 4 MB. |
| **[[ADR-0017\|ADR-0017-Taxonomia-Errores-Maquina-Estados-Watchdog-Backoff]]** | Taxonomía de Errores, FSM y Watchdog | `Accepted` | Tolerancia a Fallos | Clasificación semántica de excepciones y watchdog a 2 Hz con backoff $T = \min(2^k, 30)$ s. |
| **[[ADR-0018\|ADR-0018-Seguridad-Api-Token-Tickets-Efimeros-Proactor]]** | Seguridad Tokens y Tickets Efímeros | `Accepted` | Seguridad API | Tokens URLSafe de 32 bytes, prohibición de query tokens y tickets efímeros single-use. |
| **[[ADR-0019\|ADR-0019-Interfaz-Nativa-Escritorio-Webview2-Bandeja-Sistema]]** | Interfaz WebView2 y System Tray | `Accepted` | UI de Escritorio | Ventana nativa Edge Chromium desacoplada con bomba de mensajes Win32 y VSync a 60 FPS. |

---

## 🔍 Navegación Directa a Registros

* [[ADR-0001: MediaMTX como Broker Central|ADR-0001-Adopcion-Mediamtx-Broker-Central]]
* [[ADR-0002: Formatos DirectShow|ADR-0002-Negociacion-Dinamica-Formatos-Directshow]]
* [[ADR-0003: Cifrado Passphrase SRT|ADR-0003-Cifrado-Simetrico-Passphrase-Srt]]
* [[ADR-0004: Reloj Óptico de Código de Barras|ADR-0004-Verificador-Ineludible-Reloj-Optico-Ping]]
* [[ADR-0005: Distribución UDP Multicast|ADR-0005-Distribucion-Udp-Multicast-Unicast]]
* [[ADR-0006: Asincronía FastAPI y System Tray|ADR-0006-Desacoplamiento-Asincrono-Fastapi-System-Tray]]
* [[ADR-0007: Priorización Encoders Hardware|ADR-0007-Priorizacion-Codificadores-Hardware]]
* [[ADR-0008: Sanitización y Descripciones Canónicas|ADR-0008-Sanitizacion-Datos-Sensibles-y-Descripciones-Canonicas]]
* [[ADR-0009: Blindaje con Win32 Job Objects|ADR-0009-Blindaje-Kernel-Win32-Job-Objects]]
* [[ADR-0010: Persistencia SQLite WAL|ADR-0010-Persistencia-Transaccional-Sqlite-Wal-Migraciones]]
* [[ADR-0011: Cifrado DPAPI en Reposo|ADR-0011-Cifrado-Reposo-Credenciales-Windows-Dpapi]]
* [[ADR-0012: Prevención de Suspensión y Reloj 1 ms|ADR-0012-Prevencion-Suspension-Optimizacion-Red-Reloj-1ms]]
* [[ADR-0013: Named Mutex de Instancia Única|ADR-0013-Control-Instancia-Unica-Win32-Named-Mutex]]
* [[ADR-0014: Single-Flight Caché DirectShow|ADR-0014-Coalescencia-Single-Flight-Cache-Ttl-Hardware]]
* [[ADR-0015: Hub de Telemetría 10 Hz|ADR-0015-Hub-Reactivo-Telemetria-10hz-Bajo-Demanda]]
* [[ADR-0016: Admisión MJPEG y Extractor SOI/EOI|ADR-0016-Control-Admision-Previsualizacion-Mjpeg-On-Demand]]
* [[ADR-0017: Taxonomía de Errores y Watchdog|ADR-0017-Taxonomia-Errores-Maquina-Estados-Watchdog-Backoff]]
* [[ADR-0018: Tokens de Seguridad y Tickets|ADR-0018-Seguridad-Api-Token-Tickets-Efimeros-Proactor]]
* [[ADR-0019: Escritorio Nativo WebView2|ADR-0019-Interfaz-Nativa-Escritorio-Webview2-Bandeja-Sistema]]
