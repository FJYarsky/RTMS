# RTMS v2.6.0 — Previsualizaciones WebRTC WHEP, Canal WebSocket de Telemetría a 10 Hz, Monitoreo Determinista, Negociación MJPEG por Silicio y Escaneo Continuo Snyk

**Fecha:** 23 de Septiembre de 2026 | **Versión:** `v2.6.0`

---

### 🌐 Previsualizaciones WebRTC de Latencia Cero (<40 ms) con WHEP y Proxy Anti-CORS
- **Protocolo RFC 9397 (WHEP)**:
  - Integración nativa con MediaMTX WebRTC (`webrtc: yes`, `webrtcAddress: :8889`, `webrtcLocalUDPAddress: :8189`).
  - Visor HTML5 `<video id="preview-video">` en el frontend, eliminando la sobrecarga y latencia del streaming MJPEG en flujos activos.
  - Proxy seguro `POST /api/stream/{device_path}/whep` en FastAPI para evitar bloqueos CORS y mantener el tráfico dentro del mismo origen (`127.0.0.1:8000`).
  - Fallback automático y transparente al generador MJPEG para cámaras virtuales o flujos detenidos.

---

### ⚡ Canal WebSocket de Telemetría a 10 Hz y Eventos Reactivos
- **Ruta Asíncrona `/ws/telemetry`**:
  - `TelemetryWebSocketHub` con control de ciclo de vida: ticker de 10 Hz activo únicamente cuando hay clientes conectados (0% CPU en reposo).
  - Tasa de 10 Hz (100 ms) para métricas de video (FPS instantáneo, bitrate, dropped frames), GPU y rendimiento de red.
  - Muestreo a 1 Hz para métricas pesadas de sistema (CPU y memoria RAM).
  - Push reactivo inmediato de eventos de hardware y streaming (`device_lost`, `device_recovered`, `stream_started`, `stream_stopped`), eliminando la necesidad de polling HTTP continuo.
  - Mutación granular en tiempo real del DOM por identificador, sin re-renderizado destructivo.

---

### 📊 Monitoreo Determinista con `-progress pipe:1` (Sin Regex en Stderr)
- **Eliminación de Scraping Regex en Stderr**:
  - Inyección de `-progress pipe:1 -nostats` en el generador de comandos FFmpeg.
  - Lector asíncrono `proc.read_progress` en `StreamProc` para parseo determinista de pares `key=value` desde `stdout`.
  - Prevención garantizada de bloqueos de buffer de tubería (*pipe deadlock*) en Windows mediante drenado concurrente de `stdout` y `stderr`.
  - Contabilización precisa de fotogramas caídos (*dropped frames*) y total de frames procesados.

---

### 🔌 Negociación DirectShow MJPEG por Silicio en Webcams Físicas
- **Descompresión en el Chip Interno de la Cámara**:
  - Inyección de `-vcodec mjpeg` antes de la entrada DirectShow para dispositivos físicos.
  - Reducción de más del 95% del consumo de ancho de banda en el bus USB (de ~1000 Mbps en YUY2 sin comprimir a 25–40 Mbps en MJPEG).
  - Permite conectar 4 o más cámaras simultáneas en el mismo controlador o hub USB sin saturación de ancho de banda.

---

### 🛡️ Seguridad Continua con Snyk Security y Resolución de Dependabot
- **Escaneo Automatizado SAST & SCA**:
  - Workflow `.github/workflows/snyk.yml` para auditoría de vulnerabilidades con reporte SARIF integrado en GitHub Code Scanning.
  - Sincronización completa con `ruff >= 0.16.8` y `mypy >= 2.3.1` (absorbiendo y resolviendo Dependabot PR #13 y PR #14).
  - Resolución determinista de 68 dependencias con `uv.lock`.
  - `SECURITY.md` actualizado para soporte oficial de la versión `>= 2.6.0`.

---

### 📐 Modelos Pydantic v2 de Dominio Estricto
- **`core/config_models.py`**:
  - `CameraConfig`: validación estricta de resoluciones (`480p`, `720p`, `1080p`, `1440p`, `4K`), FPS (15–120), bitrate (500–50000 kbps), encoders y passphrases SRT (10–79 chars).
  - `SystemSettingsConfig`: validación de puertos MediaMTX (SRT, WebRTC) y ajustes del sistema.

---

### 🧪 Calidad, Verificación y Suite de Pruebas
- Suite ampliada con pruebas automatizadas completas cubriendo WebSockets, WHEP proxy, `-progress pipe:1`, modelos Pydantic v2 y workflows de CI/CD.
- Linters y formateador `ruff` validados sin advertencias.
- Preservación estricta del catálogo canónico de GitHub (32/32 [OK]).
