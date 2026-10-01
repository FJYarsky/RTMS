# Arquitectura de Sistema y Vistas C4 de RTMS

* **Versión del Sistema**: RTMS v2.8.0+
* **Estándar Documental**: Modelo C4 (Context, Containers, Components, Code)
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Clasificación**: Ingeniería de Sistemas de Misión Crítica

---

## 1. Nivel 1: Diagrama de Contexto de Sistema (System Context)

El diagrama de contexto ilustra cómo RTMS interactúa con los operadores humanos, los dispositivos de captura de video físicos del entorno local y los sistemas receptores de producción audiovisual en red.

```mermaid
flowchart TB
    operator["Operador de Transmisión<br/>(Controla encuadre, parámetros de codificación, vistas previas y orquestación)"]
    
    subgraph RTMS_SYSTEM [" Sistema RTMS (Real-Time Multicam System) "]
        rtms["RTMS Core & Services<br/>Estación multicámara de baja latencia para Windows con ingesta desacoplada, blindaje de procesos y telemetría a 10 Hz"]
    end

    cameras["Dispositivos de Entrada DirectShow<br/>(Cámaras web USB, capturadoras HDMI PCIe/USB y dispositivos virtuales)"]
    obs["OBS Studio / vMix<br/>(Software de producción en vivo y mezcla de video conectado vía SRT Listener o UDP)"]
    vlc["Reproductores VLC / LAN<br/>(Puestos de monitoreo técnico local, retorno y dispositivos móviles vía QR)"]
    browser["Navegadores Web / Control Remoto<br/>(Operadores en red local auditando video vía WebRTC WHEP y API REST)"]

    operator -->|"Configura parámetros, inicia/detiene señales y monitorea telemetría"| rtms
    cameras -->|"Entregan cuadros de video crudos o MJPEG vía DirectShow API"| rtms
    rtms -->|"Retransmite señales H.264 multiplexadas cifradas (latencia menor a 100 ms)"| obs
    rtms -->|"Emite flujos multicast y unicast de baja latencia"| vlc
    rtms -->|"Emite telemetría a 10 Hz y vistas previas en tiempo real"| browser
```

---

## 2. Nivel 2: Diagrama de Contenedores (Container Diagram)

El diagrama de contenedores desglosa la aplicación RTMS en sus entornos de ejecución, almacenes de datos y procesos concurrentes desacoplados.

```mermaid
flowchart TB
    user["Operador Técnico<br/>(Interacciona con la aplicación)"]

    subgraph RTMS_APP [" RTMS Portable Application Boundary "]
        gui["Interfaz de Usuario (SPA)<br/>HTML5, CSS3, Vanilla JS, WebRTC WHEP, WebSockets<br/>(Dashboard reactivo con telemetría HUD y modales de control)"]
        webview["Ventana Nativa WebView2<br/>pywebview / Edge Chromium Engine<br/>(Escritorio con VSync a 60 FPS y persistencia al System Tray)"]
        backend["Servidor API Backend<br/>FastAPI, Uvicorn, Python 3.12+ (asyncio)<br/>(Orquesta ciclo de vida, expone REST, autentica tokens y emite telemetría)"]
        mediamtx["Broker de Streaming Embebido<br/>MediaMTX (Go Mono-binario)<br/>(Conmutador multiplexor 1-a-N para SRT :8890, WebRTC WHEP :8889 y RTSP)"]
        workers["Workers de Ingesta FFmpeg<br/>FFmpeg 7.x/8.x (Subprocesos Win32)<br/>(Captura DirectShow, CBR y aceleración por silicio NVENC/QSV/AMF/CPU)"]
        database[("Base de Datos Transaccional<br/>SQLite WAL (config/rtms.db)<br/>(Persistencia ACID de configuración, variables y migraciones)")]
        tray["Bandeja del Sistema (System Tray)<br/>pystray, Win32 Message Pump<br/>(Icono interactivo en la barra de tareas de Windows)"]
    end

    dshow_hardware["Sensores DirectShow USB<br/>(Cámaras Físicas)"]
    clients["Clientes de Producción<br/>(OBS Studio, vMix, VLC)"]

    user -->|"Interactúa visualmente"| webview
    webview -->|"Renderiza"| gui
    gui -->|"Peticiones REST y WebSocket"| backend
    backend -->|"Lee y escribe configuraciones bajo WAL"| database
    backend -->|"Supervisa proceso y registra rutas vía REST"| mediamtx
    backend -->|"Controla ciclo de vida y lee telemetría"| workers
    backend -->|"Sincroniza eventos de detención y salida"| tray
    dshow_hardware -->|"Transfiere cuadros crudos"| workers
    workers -->|"Empuja flujos SRT multiplexados (127.0.0.1:8890)"| mediamtx
    mediamtx -->|"Distribuye flujos concurrentes sin recodificar"| clients
```

---

## 3. Nivel 3: Diagrama de Componentes del Núcleo (Component Diagram)

El diagrama de componentes detalla la estructura modular interna del backend de RTMS y la interacción entre sus administradores especializados.

```mermaid
flowchart TB
    subgraph API_BOUNDARY [" Capa de API REST (FastAPI) "]
        streams_router["StreamsRouter (api/routes/streams.py)<br/>Endpoints para arranque, parada, reinicio y estado de flujos"]
        preview_router["PreviewRouter (api/routes/preview.py)<br/>Endpoints de tickets efímeros y streaming multipart MJPEG"]
        ws_router["WebSocketRouter (api/routes/ws.py)<br/>Endpoint bidireccional /api/ws/telemetry"]
        deps["SecurityDeps (api/deps.py)<br/>Validación X-RTMS-Token, cookie HttpOnly y PreviewTicketManager"]
    end

    subgraph CORE_BOUNDARY [" Núcleo del Sistema (RTMS Core) "]
        stream_mgr["StreamManager (core/stream_manager.py)<br/>Supervisa FSM, watchdog y autorrecuperación"]
        cmd_builder["CommandBuilder (core/command_builder.py)<br/>Cadenas deterministas de flags FFmpeg CBR"]
        hw_scanner["DirectShowDeviceScanner (core/hardware.py)<br/>Coalescencia single-flight y caché TTL de 4s"]
        enc_detector["HardwareCapabilityDetector (core/hardware.py)<br/>Detección de silicio NVENC/QSV/AMF"]
        job_mgr["JobObjectManager (core/job_object.py)<br/>Win32 Job Object KILL_ON_JOB_CLOSE"]
        power_mgr["PowerManager & SystemEnv (core/power_mgr.py)<br/>Prevención de suspensión y reloj kernel a 1 ms"]
        secrets_mgr["SecretsManager (core/secrets_mgr.py)<br/>Cifrado DPAPI CryptProtectData en reposo"]
        port_mgr["PortManager (core/port_mgr.py)<br/>Asignación dinámica en rango 9000-9200"]
        preview_mgr["PreviewManager (core/preview_mgr.py)<br/>Admisión semáforo máx 3 y extracción SOI/EOI"]
        telemetry_hub["TelemetryWebSocketHub (core/telemetry_hub.py)<br/>Ticker 10 Hz on-demand y broadcast reactivo"]
        config_repo["ConfigRepository (core/repository/)<br/>Abstracción relacional SQLite WAL y migraciones"]
    end

    streams_router -->|"start_stream, stop_stream"| stream_mgr
    streams_router -->|"Verifica token de sesión"| deps
    preview_router -->|"Solicita stream MJPEG"| preview_mgr
    preview_router -->|"Consume tickets efímeros"| deps
    ws_router -->|"Registra suscriptores WebSocket"| telemetry_hub
    stream_mgr -->|"Solicita lista de argumentos"| cmd_builder
    cmd_builder -->|"Consulta mejor encoder"| enc_detector
    stream_mgr -->|"Asigna subprocesos recién creados"| job_mgr
    stream_mgr -->|"Reserva puertos de escucha"| port_mgr
    stream_mgr -->|"Obtiene y persiste configuraciones"| config_repo
    stream_mgr -->|"Sincroniza inventario físico"| hw_scanner
    config_repo -->|"Cifra passphrases al persistir"| secrets_mgr
    telemetry_hub -->|"Lee contadores de FPS y bitrate"| stream_mgr
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
        EGRESS_SRT -->|"srt://host:8890?streamid=read:{cam_id}&passphrase=..."| OBS["OBS Studio (Latencia menor a 100 ms)"]
        EGRESS_WHEP -->|"POST /whep/{cam_id} (SDP Offer/Answer)"| WEB["Dashboard HTML5 (Video Tag)"]
        EGRESS_UDP -->|"udp://@239.255.0.x:{port}"| VLC["Monitores VLC en Red Local"]
    end
```
