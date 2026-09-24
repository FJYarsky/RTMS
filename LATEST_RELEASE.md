# RTMS v2.7.0 — Ultra-Baja Latencia SRT/UDP, Zero GPU Bloat, Identidad Visual Oficial, Gobernanza Dinámica Energética y Seguridad Integral

**Fecha:** 24 de Septiembre de 2026 | **Versión:** `v2.7.0`

---

### 🚀 Motor Multimedia de Ultra-Baja Latencia y Mitigación de Saturación GPU
- **Eliminación de VBV Buffer Bloat**: Reducción del buffer VBV a sub-segundo (`bufk = int(bitrate * 0.5)k`), eliminando colas y buffers inflados que generaban latencia progresiva de varios segundos.
- **Sintonización Fina NVENC**: Ajuste exhaustivo de parámetros `h264_nvenc` (`-preset p2 -tune ll -rc cbr -delay 0 -zerolatency 1 -forced-idr 1 -bf 0 -b_adapt 0 -pix_fmt nv12`), erradicando la saturación artificial al 100% de la GPU dedicada y previniendo fallos con webcams DirectShow en formato YUYV.
- **Cadencia Determinista CFR**: Forzado de `-fps_mode cfr` antes de la codificación para sincronía estricta de marcas de tiempo PTS/DTS.
- **Optimización de Sockets UDP y Mapeo Multicast Inyectivo**: Buffers de red configurados a `buffer_size=131072` (128 KB) y `fifo_size=50000`. Fórmula inyectiva `(port - 9000) + 1` asignando IPs de multidifusión únicas (`239.255.0.1`..`239.255.0.201`) para puertos 9000..9200, garantizando cero colisiones.
- **Latencia Sub-100ms en Clientes SRT y VLC**: Receptores SRT con URLs de reproducción directa sin búfer retardado en OBS/vMix y VLC. Formato canónico `udp://@:<port>` para VLC UDP Unicast LAN.
- **Watchdog Anti-Freeze**: Monitoreo de `last_progress_at` con reinicio automático si la transmisión se congela (>10s sin avance de frames).

---

### 💾 Persistencia Transaccional SQLite v2 y Semántica REST PATCH
- **Migración de Base de Datos a Esquema v2**: Soporte nativo para persistir `is_virtual`, `udp_mode` y `udp_host` de forma idempotente y segura (ACID WAL).
- **Semántica PATCH Granular**: Actualización de cámaras preservando campos omitidos y control seguro de credenciales SRT (`secret_action = keep | set | clear`).
- **Arquitectura No-Mutante en StreamManager**: `get_proc` retorna `None` / HTTP 404 para cámaras inexistentes, previniendo asignaciones residuales de puertos y procesos fantasma.
- **Reinicio Selectivo Inteligente**: Las importaciones de configuración en caliente sólo reinician procesos cuando los parámetros del pipeline de codificación han cambiado.

---

### 🎨 Identidad Visual Oficial, Estética y Branding Vectorial
- **Badge de Versión Fluorescente**: Píldora `.version-tag` rediseñada con tipografía monospace fluorescente (JetBrains Mono/Consolas), halo de luz sutil y micro-interacción hover.
- **HUD Superior y Animación de Tarjetas**: Indicadores en vivo en la barra de navegación con animación esmeralda pulsante `pulse-live` para transmisiones activas.
- **Modal "Acerca de" con Imagotipo Vectorial**: Integración de `gui/static/imagotype_vertical.svg`, tarjeta glassmorphism de autor y enlace directo a la web oficial `https://fjyarsky.github.io/RTMS/`.
- **Selector de Protocolo y Modal QR**: Experiencia pulida con selección directa de "UDP Unicast LAN" y host destino.

---

### 🛡️ Seguridad Integral, Prevención de Fugas y Gobernanza de Energía
- **Eliminación de Tokens en Query Strings (CWE-598)**: Rechazo explícito con HTTP 403 en previsualizaciones WHEP y código 1008 en `/ws/telemetry`. Autenticación obligatoria mediante cookies de sesión HttpOnly `rtms_session` o cabeceras `X-RTMS-Token`.
- **Prevención de Fuga de Handles Win32**: Invocación garantizada de `CloseHandle` en bloques `finally` en el gestor de Job Objects.
- **Gobernador Dinámico de Energía**: Activación automática del plan de Alto Rendimiento en Windows durante streaming activo y restauración del esquema previo al detener flujos.
- **Cabeceras CSP**: Inyección de `Content-Security-Policy` estricto en respuestas HTTP.
- **Redirección de Logs MediaMTX**: Redirección segura a `config/mediamtx.log` con rotación preventiva (5 MB).
- **Operaciones No Bloqueantes**: Envoltura de comandos `powercfg` y tareas de I/O en hilos asíncronos vía `asyncio.to_thread`.

---

### 🧪 Suite de Pruebas y Control de Calidad
- **186/186 Pruebas Automatizadas Pasando al 100%**: Cobertura exhaustiva de endpoints, pipeline multimedia, base de datos, persistencia, seguridad y rendimiento.
- **0 Errores de Mypy en 41 Archivos Fuente**: Verificación de tipado estricto completada.
- **Linter y Formato 100% Limpio**: Ruff check y ruff format sin advertencias.

