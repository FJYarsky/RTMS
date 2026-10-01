# Arquitectura de Sistema y Vistas C4 de RTMS

* **Versión del Sistema**: RTMS v2.8.0+
* **Estándar Documental**: Modelo C4 (Context, Containers, Components, Code)
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Clasificación**: Ingeniería de Sistemas de Misión Crítica

---

## 1. Nivel 1: Diagrama de Contexto de Sistema (System Context)

El diagrama de contexto ilustra cómo RTMS interactúa con los operadores humanos, los dispositivos de captura de video físicos del entorno local y los sistemas receptores de producción audiovisual en red.

```mermaid
C4Context
    title Diagrama de Contexto de Sistema — RTMS (Real-Time Multicam System)

    Person(operator, "Operador de Transmisión", "Controla el encuadre, parámetros de codificación, previsualización y orquestación de cámaras.")
    
    System(rtms, "RTMS", "Estación de transmisión multicámara de baja latencia para Windows con ingesta desacoplada, blindaje de procesos y telemetría a 10 Hz.")

    System_Ext(cameras, "Dispositivos de Entrada DirectShow", "Cámaras web USB, capturadoras HDMI PCIe/USB y dispositivos virtuales de video.")
    System_Ext(obs, "OBS Studio / vMix", "Software de producción en vivo y mezcla de video conectado vía SRT (Caller) o UDP.")
    System_Ext(vlc, "Reproductores VLC / LAN", "Puestos de monitoreo técnico local, monitores de retorno y dispositivos móviles vía QR.")
    System_Ext(browser, "Navegadores Web / Control Remoto", "Operadores remotos en la misma LAN auditando video vía WebRTC WHEP y API REST.")

    Rel(operator, rtms, "Configura parámetros, inicia/detiene señales y monitorea telemetría", "HTTPS / WebSocket / GUI")
    Rel(cameras, rtms, "Entregan cuadros de video crudos o MJPEG", "DirectShow API / USB Bus")
    Rel(rtms, obs, "Retransmite señales H.264 multiplexadas cifradas (<100 ms)", "SRT Listener (AES-128)")
    Rel(rtms, vlc, "Emite flujos multicast y unicast de baja latencia", "UDP / SRT")
    Rel(rtms, browser, "Emite telemetría a 10 Hz y vistas previas en tiempo real", "WebRTC WHEP / MJPEG Multipart")
```

---

## 2. Nivel 2: Diagrama de Contenedores (Container Diagram)

El diagrama de contenedores desglosa la aplicación RTMS en sus entornos de ejecución, almacenes de datos y procesos concurrentes desacoplados.

```mermaid
C4Container
    title Diagrama de Contenedores — RTMS

    Person(user, "Operador Técnico", "Interacciona con la aplicación")

    Container_Boundary(rtms_app, "RTMS Portable Application Boundary") {
        Container(gui, "Interfaz de Usuario (SPA)", "HTML5, CSS3, Vanilla JS, WebRTC WHEP, WebSockets", "Dashboard reactivo con telemetría HUD, gestión de cámaras y modales de configuración.")
        Container(webview, "Ventana Nativa WebView2", "pywebview / Edge Chromium Engine", "Ejecutable de escritorio con control de VSync (60 FPS) y persistencia al System Tray.")
        Container(backend, "Servidor API Backend", "FastAPI, Uvicorn, Python 3.12+ (asyncio)", "Orquesta el ciclo de vida, expone endpoints REST, autentica mediante tokens y distribuye telemetría a 10 Hz.")
        Container(mediamtx, "Broker de Streaming Embebido", "MediaMTX (Go Mono-binario)", "Conmutador de paquetes multiplexor 1-a-N para SRT (:8890), WebRTC WHEP (:8889) y RTSP.")
        Container(workers, "Workers de Ingesta FFmpeg", "FFmpeg 7.x/8.x (Subprocesos Win32)", "Capturan DirectShow, aplican rate control CBR y codifican con aceleración por silicio (NVENC/QSV/AMF/CPU).")
        ContainerDb(database, "Base de Datos Transaccional", "SQLite WAL (config/rtms.db)", "Persistencia ACID de configuración de cámaras, parámetros globales y migraciones de esquema.")
        Container(tray, "Bandeja del Sistema (System Tray)", "pystray, Win32 Message Pump", "Icono interactivo de notificación en la barra de tareas de Windows para control en segundo plano.")
    }

    System_Ext(dshow_hardware, "Sensores DirectShow USB", "Cámaras Físicas")
    System_Ext(clients, "Clientes de Producción", "OBS Studio, vMix, VLC")

    Rel(user, webview, "Interactúa visualmente", "Win32 Window")
    Rel(webview, gui, "Renderiza", "Chromium DOM")
    Rel(gui, backend, "Peticiones REST y WebSocket", "HTTP / WS (localhost:8000)")
    Rel(backend, database, "Lee y escribe configuraciones bajo WAL", "SQL (aiosqlite / sqlite3)")
    Rel(backend, mediamtx, "Supervisa proceso y registra rutas vía REST", "HTTP Control / Win32 Job Object")
    Rel(backend, workers, "Controla ciclo de vida y lee telemetría", "asyncio.subprocess / stdout pipe:1")
    Rel(backend, tray, "Sincroniza eventos de detención y salida", "Threadsafe callbacks")
    Rel(dshow_hardware, workers, "Transfiere cuadros crudos", "DirectShow Drivers")
    Rel(workers, mediamtx, "Empuja flujos SRT multiplexados", "SRT Loopback (127.0.0.1:8890)")
    Rel(mediamtx, clients, "Distribuye flujos concurrentes sin recodificar", "SRT AES-128 / WebRTC / UDP")
```

---

## 3. Nivel 3: Diagrama de Componentes del Núcleo (Component Diagram)

El diagrama de componentes detalla la estructura modular interna del backend de RTMS y la interacción entre sus administradores especializados.

```mermaid
C4Component
    title Diagrama de Componentes — RTMS Core & API

    Container_Boundary(core_boundary, "Núcleo del Sistema (RTMS Core)") {
        Component(stream_mgr, "StreamManager", "core/stream_manager.py", "Supervisa la FSM de cada stream, ejecuta el watchdog de autorrecuperación y orquesta los reinicios.")
        Component(cmd_builder, "CommandBuilder", "core/command_builder.py", "Calcula cadenas deterministas de flags para FFmpeg con calibración CBR y optimización de latencia.")
        Component(hw_scanner, "DirectShowDeviceScanner", "core/hardware.py", "Sondea dispositivos mediante coalescencia single-flight y caché TTL de 4 segundos.")
        Component(enc_detector, "HardwareCapabilityDetector", "core/hardware.py", "Detecta aceleradores de silicio (NVENC, QSV, AMF) con caché de prueba única en el arranque.")
        Component(job_mgr, "JobObjectManager", "core/job_object.py", "Blinda los subprocesos en el kernel con JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.")
        Component(power_mgr, "PowerManager & SystemEnv", "core/power_mgr.py", "Previene suspensión del SO, ajusta PnPCapabilities de red y fija el reloj del kernel a 1 ms.")
        Component(secrets_mgr, "SecretsManager", "core/secrets_mgr.py", "Cifra y descifra credenciales en reposo mediante Windows DPAPI (CryptProtectData).")
        Component(port_mgr, "PortManager", "core/port_mgr.py", "Asigna y revalida sockets libres en el rango 9000-9200, resolviendo colisiones.")
        Component(preview_mgr, "PreviewManager", "core/preview_mgr.py", "Controla la admisión (máximo 3) y extrae fragmentos JPEG delimitados por cabeceras SOI/EOI.")
        Component(telemetry_hub, "TelemetryWebSocketHub", "core/telemetry_hub.py", "Ejecuta el ticker de 10 Hz activado por demanda y notifica eventos reactivos.")
        Component(config_repo, "ConfigRepository", "core/repository/", "Capa de abstracción relacional sobre SQLite con migraciones idempotentes.")
    }

    Container_Boundary(api_boundary, "Capa de API REST (FastAPI)") {
        Component(streams_router, "StreamsRouter", "api/routes/streams.py", "Endpoints para arranque, parada, reinicio y estado de flujos.")
        Component(preview_router, "PreviewRouter", "api/routes/preview.py", "Endpoints de generación de tickets efímeros y streaming multipart.")
        Component(ws_router, "WebSocketRouter", "api/routes/ws.py", "Endpoint bidireccional /api/ws/telemetry.")
        Component(deps, "SecurityDeps", "api/deps.py", "Validación de cabecera X-RTMS-Token, cookie HttpOnly y PreviewTicketManager.")
    }

    Rel(streams_router, stream_mgr, "Invoca start_stream, stop_stream")
    Rel(streams_router, deps, "Verifica token de sesión")
    Rel(preview_router, preview_mgr, "Solicita stream MJPEG y valida slots")
    Rel(preview_router, deps, "Consume tickets efímeros")
    Rel(ws_router, telemetry_hub, "Registra suscriptores WebSocket")
    Rel(stream_mgr, cmd_builder, "Solicita lista de argumentos")
    Rel(cmd_builder, enc_detector, "Consulta mejor encoder")
    Rel(stream_mgr, job_mgr, "Asigna subprocesos recién creados")
    Rel(stream_mgr, port_mgr, "Reserva puertos de escucha")
    Rel(stream_mgr, config_repo, "Obtiene y persiste configuraciones")
    Rel(stream_mgr, hw_scanner, "Sincroniza inventario físico")
    Rel(config_repo, secrets_mgr, "Cifra passphrases al persistir")
    Rel(telemetry_hub, stream_mgr, "Lee contadores de FPS y bitrate")
```

---

## 4. Nivel 4: Diagrama de Código y Ejecución del Pipeline (Code / Pipeline View)

El diagrama de código modela la secuencia detallada de procesamiento de un cuadro de video desde su captura en el sensor USB hasta su entrega final al cliente SRT.

```mermaid
flowchart TD
    subgraph DSHOW [" Capa Física DirectShow "]
        USB["Sensor CMOS / Lente USB"] -->|"Cuadros Crudos (YUYV) o MJPEG"| DRV["Controlador USB Win32"]
        DRV -->|"DirectShow Source Filter"| PIN{"Evaluación de Pin de Sensor"}
        PIN -->|"MJPEG Soportado (ADR-0002)"| M_PIN["-vcodec mjpeg -rtbufsize 100M"]
        PIN -->|"Solo RAW (NV12 / YUY2)"| R_PIN["-pixel_format yuyv422 -rtbufsize 65M"]
    end

    subgraph WORKER [" Worker FFmpeg (Subproceso Aislado) "]
        M_PIN --> DEC["Decodificador de Entrada"]
        R_PIN --> DEC
        DEC -->|"Buffer de Píxeles Crudos"| FLT["Filtro de Escala y Tasa (fps=30, scale=1280x720)"]
        FLT --> ENC{"Codificador Asignado"}
        
        ENC -->|"NVIDIA NVENC"| E_NV["h264_nvenc -preset p1 -tune ll -rc cbr -zerolatency 1"]
        ENC -->|"Intel QSV"| E_QSV["h264_qsv -preset veryfast -async_depth 1"]
        ENC -->|"AMD AMF"| E_AMF["h264_amf -usage lowlatency -quality speed"]
        ENC -->|"CPU Fallback"| E_CPU["libx264 -preset ultrafast -tune zerolatency"]
        
        E_NV --> CBR["Buffer VBV: maxrate=bitrate*1.15, bufsize=bitrate*0.35"]
        E_QSV --> CBR
        E_AMF --> CBR
        E_CPU --> CBR

        CBR --> GOP["Cadencia IDR Forzada: -g max(15, fps*0.5)"]
        GOP --> MUX["Multiplexor MPEG-TS (pkt_size=1316)"]
        MUX --> PUSH["SRT Socket Client (mode=caller, tlpktdrop=1, latency=50ms)"]
    end

    subgraph BROKER [" MediaMTX Server (Broker Central) "]
        PUSH -->|"srt://127.0.0.1:8890?streamid=publish:{cam_id}"| INGEST_SOCK["Socket de Ingesta SRT"]
        INGEST_SOCK --> ROUTE["Tabla de Enrutamiento de Rutas en Memoria"]
        ROUTE --> EGRESS_SRT["SRT Listener (:8890) con Passphrase AES-128"]
        ROUTE --> EGRESS_WHEP["WebRTC HTTP Egress Protocol WHEP (:8889)"]
        ROUTE --> EGRESS_UDP["UDP Forwarder (:8888 / Multicast 239.255.0.x)"]
    end

    subgraph CLIENTS [" Receptores de Producción "]
        EGRESS_SRT -->|"srt://host:8890?streamid=read:{cam_id}&passphrase=..."| OBS["OBS Studio (Latencia <100ms)"]
        EGRESS_WHEP -->|"POST /whep/{cam_id} (SDP Offer/Answer)"| WEB["Dashboard HTML5 (Video Tag)"]
        EGRESS_UDP -->|"udp://@239.255.0.x:{port}"| VLC["Monitores VLC en Red Local"]
    end
```
