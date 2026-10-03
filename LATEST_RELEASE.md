# RTMS v2.8.3 — Estandarización a 60 FPS, Pinning a P-Cores, Enlace Directo OBS y Estabilización General

**Fecha:** 3 de Octubre de 2026 | **Versión:** `v2.8.3`

---

### ⚡ Rendimiento, 60 FPS y Planificación de CPU
- **Estandarización Global a 60 FPS**: Se establece 60 FPS como el valor predeterminado en todos los presets de cámara, esquemas de persistencia y base de datos SQLite WAL (migración v3). Se implementa auto-negociación defensiva: si un sensor físico solo admite 30 FPS, conmuta transparentemente sin abortar.
- **Pinning Automático a P-Cores (Windows NT CPU Affinity)**: Detección nativa de topología híbrida mediante `GetLogicalProcessorInformationEx` (`RelationProcessorCore`, `EfficiencyClass`) en `core/process_optimizer.py`. FFmpeg y MediaMTX se aíslan automáticamente en los Performance Cores para erradicar el jitter y caídas de frames causadas por la migración a E-Cores.
- **Bloqueo Inteligente de Auto-Exposición UVC**: Módulo `core/uvc_control.py` con interfaz DirectShow COM `IAMCameraControl` forzando tiempo de obturación manual $\le 1/60\text{ s}$ al iniciar la cámara, evitando caídas silenciosas a 15-20 FPS en penumbra.
- **Lazy Startup de MediaMTX**: Desacoplado el arranque incondicional en lifespan; MediaMTX ahora se inicia bajo demanda únicamente cuando hay flujos SRT o sesiones WebRTC activas, y se apaga suavemente tras un período de gracia de 20 segundos de inactividad total (ahorro de ~50 MB RAM y puertos libres).

---

### 🛠️ Correcciones Críticas de OBS Studio, Red y Aspect Ratio
- **Sintaxis de URL Directa para OBS Studio (Eliminación de `@`)**: En modo UDP Unicast, las URLs provistas para el receptor ahora generan estrictamente `udp://<IP_RECEPTOR>:<PUERTO>` (o `udp://127.0.0.1:<PUERTO>` en loopback), erradicando la sintaxis `udp://@:puerto` que fallaba en la Fuente Multimedia de OBS.
- **Persistencia y Visualización Inmediata de IP de Destino**: Corregido el bug crítico en `app.js` (`confirmAndStartUnicast()`) que enviaba `protocol: 'udp_unicast'` rechazado con HTTP 422 por FastAPI. Ahora se persiste adecuadamente en SQLite y se renderiza en la tarjeta de la cámara de inmediato.
- **Corrección de Deformación de Aspect Ratio (4:3 a 16:9 en 1080p)**: Detección y priorización de compresión MJPEG (`-vcodec mjpeg`) para webcams USB 2.0 que rechazan 1080p NV12, sumado a filtro de reescalado defensivo con preservación de relación de aspecto (`force_original_aspect_ratio=decrease,pad=...`) para evitar el estiramiento horizontal de la imagen.
- **Búfer Seguro Anti-Congelamiento para VLC (300 ms)**: Búfer predeterminado de red en VLC ajustado a 300 ms (mínimo seguro $\ge 250\text{ ms}$) y erradicación total de las banderas desestabilizadoras `:clock-jitter=0 :clock-synchro=0` que congelaban el reproductor.
- **Degradación de SRT y UDP Unicast como Recomendado**: Retirada la etiqueta "Recomendado" a SRT debido a sus inestabilidades y cuelgues con MediaMTX/gosrt; UDP Unicast queda fijado como el protocolo predeterminado y recomendado para redes locales.
- **Transporte Optativo Raw RTP**: Nuevo protocolo `rtp` con generación automática de descriptores `.sdp` para OBS Studio.
- **Saneamiento de Promesas de Latencia**: Purgadas afirmaciones engañosas de `<100ms real sin buffers` o `50ms en VLC`, sustituyéndolas por descripciones técnicas transparentes del modo Zerolatency.

---

### 🛡️ Calidad y Validación
- **390 Pruebas Automatizadas Pasando (100% éxito)**: Cobertura integral en suites unitarias y de integración sin regresiones.
- **Benchmark Local de Ping Verificado**: 0.108 ms ping promedio en UDP loopback, 100% paquetes entregados sin pérdidas.
- **Repositorio Sanitizado y Código Limpio**: 0 advertencias en Ruff, Mypy y sanitizador del repositorio.
