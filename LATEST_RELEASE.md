# RTMS v2.2.6 — Corrección Crítica de Conexión SRT, Optimización UDP 1080p60 y Suite de Diagnóstico FFmpeg

**Fecha de lanzamiento:** 17 de Septiembre de 2026  
**Etiqueta:** `v2.2.6`

---

### 🛠️ Corrección Crítica de Entablado de Conexión SRT y Copia de URL
- **Resolución Definitiva de Rechazo por Contraseña Faltante (`ERROR:UNSECURE`)**:
  - RTMS genera passphrases criptográficas seguras al registrar cámaras, pero la interfaz web copiaba la URL `srt://IP:port?mode=caller...` omitiendo el parámetro `&passphrase=...`. Sockets externos como OBS Studio o vMix eran rechazados inmediatamente con `ERROR:UNSECURE (Password required or unexpected)`.
  - Se implementó el endpoint protegido `GET /api/stream/{device_path}/connect_url` en `api/routes.py` que calcula y devuelve la URL completa, normalizada y funcional con su passphrase configurada y codificación de caracteres especiales (`urllib.parse.urlencode`).
  - Se actualizó `gui/static/app.js` (`copyUrlByIndex`) para consultar este endpoint al pulsar "Copiar URL", copiando al portapapeles la dirección exacta y garantizando la conexión al 100%.
- **Resiliencia del Listener SRT ante Desconexiones de Clientes**:
  - En `core/ffmpeg_mgr.py`, el Watchdog detecta cuando FFmpeg finaliza tras la desconexión normal de un cliente receptor (`-5 I/O error` / `muxer`) y reinicia el proceso listener de inmediato con penalización cero y sin retardos de *backoff*, dejando el socket disponible para reconexión instantánea.

---

### 🚀 Optimización y Estabilidad Continua de Streaming UDP a 1080p @ 60 FPS
- **Ampliación de Buffer de Socket de Red a 4 MB**:
  - El buffer de socket UDP en `core/ffmpeg_mgr.py` (`build_multicast_url`) se incrementó de 64 KB (`buffer_size=65535`) a 4 MB (`buffer_size=4194304&overrun_nonfatal=1&fifo_size=50000000`). Esto elimina la saturación de socket en Windows a altas tasas de bits (6–12 Mbps) y erradica por completo la pérdida de paquetes y tirones de framerate.
- **Inyección Forzada de Cabeceras SPS/PPS (`repeat-headers` y `dump_extra`)**:
  - Se añadieron los parámetros `-x264-params repeat-headers=1` (para CPU `libx264`) y `-forced-idr 1` (para GPU `h264_nvenc`), combinados con el bitstream filter `-bsf:v dump_extra` para MPEG-TS. Receptores que conectan con la transmisión ya iniciada reciben de inmediato los parámetros de secuencia sin arrojar errores `non-existing PPS 0 referenced`.
- **Soporte Nativo de Fuentes de Cámara Virtual (`virtual://` / `testsrc`)**:
  - `core/ffmpeg_mgr.py` ahora admite cámaras virtuales `virtual://` que generan patrones sintéticos `testsrc2` en tiempo real, permitiendo transmitir y verificar 1080p60 continuo en hardware de test o sin cámara física 60fps.

---

### 🔬 Suite Integral de Diagnóstico, Digestión de Video y Pruebas en Vivo
- **Motor de Análisis y Digestión en Tiempo Real (`core/ffmpeg_tester.py`)**:
  - `VideoReceiverDigest`: Receptor y analizador de flujos en vivo que decodifica flujos SRT y UDP con `-progress pipe:1`, calculando FPS decodificados reales, bitrate instantáneo, estabilidad de jitter, frames descartados y errores de bitstream H.264.
  - `VirtualCameraSource`: Generador de video sintético calibrado con patrones `testsrc2`, barras SMPTE y reloj OSD con microsegundos a cualquier resolución y framerate.
  - `FFmpegDiagnosticSuite`: Orquestador de pruebas locales que valida binarios, códecs de hardware (NVENC/x264), dispositivos DirectShow y entablado de conexiones en bucle local (loopback).
- **Herramienta CLI de Consola (`scripts/test_ffmpeg_pipeline.py`)**:
  - CLI interactivo y automatizado con soporte nativo UTF-8 en consolas Windows, banderas de diagnóstico (`--all`, `--srt`, `--udp`, `--bench`, `--camera`, `--virtual-cam`).
- **Tests Automatizados de Integración (`tests/test_ffmpeg_live.py`)**:
  - 5 tests de integración en vivo añadidos a la suite oficial de Pytest, elevando la cobertura a 113 tests unitarios y de integración pasando al 100%.
