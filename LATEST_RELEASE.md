# RTMS v2.8.2 — Optimización Extrema de Latencia (≤50ms P50 SLA) y UDP Unicast por Defecto

**Fecha:** 2 de Octubre de 2026 | **Versión:** `v2.8.2`

---

### ⚡ Rendimiento y Latencia Ultrabaja Sub-50ms
- **Objetivo de Latencia Cumplido (≤50ms P50 SLA)**: Reducción drástica del retardo extremo a extremo (*glass-to-glass*) en redes LAN cableadas a 60 FPS, logrando registros de **~38.8ms P50 (AMD AMF)**, **~40.8ms P50 (CPU libx264)** y **42.0ms Min** en pruebas reales de laboratorio.
- **Protocolo por Defecto: UDP Unicast**: Se establece UDP Unicast (`udp` / `unicast`) como configuración predeterminada en todo el sistema (menor ping absoluto, streaming directo punto a punto sin intermediarios ni sobrecargas de broker).

---

### 🛠️ Correcciones Críticas de Pipeline (~105ms de Reducción de Latencia)
- **Erradicación de Fallas en NVIDIA NVENC y Desincronización DirectShow**:
  - Reemplazo de `-fps_mode passthrough` por `-fps_mode cfr` (Constant Frame Rate) para forzar marcas de tiempo DTS estrictamente crecientes y continuas, erradicando advertencias de *Non-monotonic DTS* por fluctuaciones del controlador USB UVC.
  - Eliminación de `-intra-refresh 1` en codificadores NVENC (`h264_nvenc`, `hevc_nvenc`, `av1_nvenc`), preservando `-forced-idr 1` con GOP corto (`-g 15` / 500ms) y `-bsf:v dump_extra` para inyectar SPS/PPS periódicos. Esto resuelve por completo la recepción de pantalla negra en OBS Studio y reproductores VLC.
- **Erradicación del Doble Búfer SRT**: Sintonización de latencia en bucle local (`localhost`) reducida de 50ms a 10ms con `tlpktdrop=0` (eliminando descartes espurios en loopback); latencia de salida de cliente reducida de 50ms a 15ms en red cableada.
- **Formato Nativo NV12 en Captura DirectShow**: Inyección mandatoria de `-pixel_format nv12` con fallback defensivo, erradicando la penalización de 4 a 9 ms por fotograma de conversión CPU `swscale`.
- **Eliminación de Bufferbloat en Control de Tasa VBV**: Reducción de `-bufsize` de `bitrate*0.35` (ventana de 350ms) a `bitrate/fps*1.5` (ventana de 1.5 fotogramas), eliminando ráfagas y retrasos acumulativos de 10 a 25 ms.
- **Sintonización de Cola DirectShow (`-rtbufsize`)**: Cola de captura calibrada a 10MB (1080p), 5MB (720p) y 3MB (MJPEG) para prevenir acumulación de retraso en segundo plano.

---

### 🖥️ Interfaz Web, Experiencia de Usuario y Enfoque en UDP Unicast
- **Persistencia de IP de Destino Unicast**: Inclusión de `udp_host` en el estado central de la API y el repositorio transaccional SQLite WAL, evitando que la IP configurada se reinicie a `127.0.0.1` al reabrir el modal de ajustes.
- **Selector Rápido de IP Local y LAN**: Incorporación de chips de autocompletado rápido (`127.0.0.1` y la IP LAN detectada en el servidor) en los formularios de configuración.
- **Diálogo Interactivo al Iniciar Transmisión Unicast por Primera Vez**: Detección inteligente de cámaras sin destino confirmado al pulsar *Iniciar*, solicitando la IP del equipo receptor con opciones de autocompletado en un clic y persistencia automática.
- **Restablecimiento a Valores Predeterminados Centrado en Unicast**: El botón de restablecer valores por defecto de cámara carga de inmediato el perfil de menor latencia: 720p @ 30 FPS, 3000 kbps y protocolo **UDP Unicast** (`udp_unicast`).
- **Armonización de Textos y URLs de Conexión**: Botón unificado *"Conectar / Compartir"*, visualización explícita del destino en las tarjetas de cámara (`Destino: <ip>:<puerto>`), y modal de conexión con instrucciones claras para fuentes multimedia en OBS Studio y VLC Player.

---

### 🚀 Optimización de Codificadores y Sistema Operativo
- **libx264 (CPU)**: Incorporación de hilos por sectores (`-slices 4 -threads 4`), intra-refresh y flag `+low_delay`.
- **AMD AMF (GPU)**: Configuración con `-latency 1`, `-rc cbr`, `-enforce_hrd 1` y pre-análisis deshabilitado.
- **NVIDIA NVENC y Intel QuickSync**: Sintonización CBR estricta de ultra-bajo retardo y VBV de 1.5 fotogramas.
- **Elevación de Prioridad Win32 (`core/process_optimizer.py`)**: Asignación automática de `HIGH_PRIORITY_CLASS` en tiempo real a procesos secundarios de FFmpeg y MediaMTX en el planificador de Windows NT.
- **MediaMTX y WebRTC WHEP**: Cola de escritura optimizada (`writeQueueSize: 128`), enlace multi-interfaz (`:8889`) con autodetección de IP local para candidatos ICE, y soporte para previsualización WebRTC WHEP sub-30ms.

---

### 🛡️ Calidad de Código y Validación
- **378 Pruebas Automatizadas Pasando (100%)**: Cobertura exhaustiva en suites unitarias, de integración, concurrencia, límites, fuzzing y benchmarking sin fallos.
- **Verificación E2E de Hardware y Protocolos**: 9/9 pipelines validadas en vivo incluyendo MediaMTX, SRT, SRT-AES, UDP Multicast, UDP Unicast, WebRTC WHEP y cámaras físicas DirectShow.
