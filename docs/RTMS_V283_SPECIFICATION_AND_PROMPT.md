# RTMS v2.8.3 — Especificación Técnica y Prompt de Implementación

> **Versión Objetivo:** RTMS v2.8.3  
> **Fecha de Elaboración:** 3 de Octubre de 2026  
> **Ámbito:** Optimización táctica, corrección de bugs críticos de estabilidad/UI y mejoras sobre la arquitectura existente (Python 3.12, FastAPI, FFmpeg CLI, DirectShow, MediaMTX, pywebview, SQLite).  
> **Documento Asociado:** `docs/RTMS_V290_SPECIFICATION_AND_PROMPT.md` (Para la reestructuración mayor de arquitectura).

---

## 1. Resumen Ejecutivo y Objetivos de la v2.8.3

La versión 2.8.3 tiene como objetivo estabilizar, corregir y optimizar la experiencia de transmisión de ultra-baja latencia sin romper la compatibilidad con el ecosistema actual de RTMS. Aborda directamente las deficiencias detectadas en producción con OBS Studio, VLC y MediaMTX/SRT, a la vez que introduce las optimizaciones tácticas del sistema operativo Windows NT (P-Cores, 60 FPS, bloqueo de auto-exposición UVC y arranque bajo demanda de MediaMTX).

---

## 2. Diagnóstico y Correcciones de Problemas Reportados en Producción

### 2.1. Sintaxis de URL para OBS Studio: Eliminación de `@` y Uso de IP del Receptor
* **Problema:** En `core/stream_proc.py:187` y `gui/static/app.js:637, 2191`, cuando el destino no es localhost, la URL generada para el cliente era `udp://@:puerto`. En OBS Studio (Fuente Multimedia basada en libavformat), la sintaxis con `@` está pensada para sockets de escucha multicast o comodín de interfaz, pero genera fallos de enlace y ambigüedad en redes locales.
* **Solución Técnica:**
  - En transmisiones UDP Unicast, la URL provista para el equipo receptor OBS debe ser explícitamente `udp://<IP_DEL_RECEPTOR>:<PUERTO>` (o `udp://127.0.0.1:<PUERTO>` si es loopback).
  - Actualizar `build_client_urls()` en `core/stream_proc.py`, la vista de tarjetas en `gui/static/app.js` y el modal de conexión para OBS para que nunca inyecten `@` en modo Unicast.

### 2.2. Error de Persistencia y Visualización de la IP del Receptor (`udp_host`)
* **Problema:**
  - En `gui/static/app.js:1081`, la función `confirmAndStartUnicast()` enviaba:
    ```javascript
    payload = { ... protocol: 'udp_unicast', udp_host: targetIp };
    ```
  - En `api/schemas.py:33`, el modelo `CameraConfigUpdate` define estrictamente:
    ```python
    protocol: Optional[Literal["srt", "udp"]] = None
    ```
  - Al recibir `'udp_unicast'`, FastAPI/Pydantic rechazaba la solicitud con **HTTP 422 Unprocessable Entity**.
  - Como resultado, el backend **nunca guardaba la IP del receptor** en disco ni en SQLite. La UI solo la mantenía momentáneamente en memoria local, y al refrescar o recargar la página, volvía a mostrar `127.0.0.1`.
* **Solución Técnica:**
  - Corregir `gui/static/app.js:1081` para que envíe `protocol: 'udp'` y `udp_mode: 'unicast'`.
  - Asegurar que `update_stream_config_endpoint` persista `udp_host` en SQLite y en `proc.config`.
  - Asegurar que la tarjeta de la cámara (`renderStreamCards`) renderice `Destino: <udp_host>:<port>` de forma reactiva e inmediata.

### 2.3. Corrección de Distorsión de Aspect Ratio 4:3 a 16:9 en 1080p
* **Problema:**
  - Muchas webcams USB 2.0 no soportan 1080p en espacio de color YUY2/NV12 sin comprimir debido a las limitaciones del bus USB 2.0 (480 Mbps). Solo soportan 1080p mediante compresión **MJPEG**.
  - Cuando el usuario configuraba 1080p, RTMS solicitaba el pin NV12 (`-pixel_format nv12 -video_size 1920x1080`). El driver DirectShow rechazaba esta configuración, activando el manejador de fallo `dshow_options_failed`.
  - Al reintentar, FFmpeg abría la cámara sin especificar `-video_size`, lo que hacía que la cámara iniciara en su modo nativo predeterminado (frecuentemente **640x480 a 4:3**).
  - Posteriormente, FFmpeg aplicaba `-vf scale=1920x1080`, estirando forzadamente el fotograma 4:3 a 16:9, deformando rostros y objetos.
* **Solución Técnica:**
  - Al solicitar 1080p, forzar automáticamente la solicitud del pin MJPEG (`-vcodec mjpeg`) si la cámara es USB y lo expone.
  - En la construcción de filtros de reescalado fallback, nunca forzar `scale=W:H` plano; utilizar escalado con preservación de relación de aspecto y relleno si fuera estrictamente necesario:
    ```
    scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black
    ```

### 2.4. Congelamiento de VLC con `:network-caching` menor a 250 ms
* **Problema:**
  - El demuxer de MPEG-TS de VLC (`ts.c`) requiere acumular tablas PAT/PMT y PCR continuos.
  - Al configurarse flags extremas como `:clock-jitter=0 :clock-synchro=0` con `:network-caching=50`, cualquier fluctuación de milisegundos en el buffer de sockets de Windows causa inanición del decodificador de video de VLC, congelando la imagen indefinidamente.
* **Solución Técnica:**
  - Fijar el valor predeterminado de `:network-caching` para VLC en **300 ms** (con umbral mínimo seguro recomendado de 250 ms en UI y scripts).
  - Eliminar las directivas desestabilizadoras `:clock-jitter=0` y `:clock-synchro=0` del comando generado para VLC en `core/stream_proc.py`, `app.js` y `vlc_playlist.xspf`.
  - Documentar en la UI que VLC es un reproductor de monitoreo con buffer de seguridad de 250-300 ms, recomendando OBS Studio (con Fuente Multimedia y buffer reducido) para latencia sub-100 ms.

### 2.5. Degradación de SRT y Eliminación de Etiqueta "Recomendado"
* **Problema:**
  - SRT sobre MediaMTX (gosrt) presenta inestabilidades, sobrecarga en loopback, desconexiones estocásticas con `ERROR:ROGUE` y bloqueos ante jitter de red local.
  - En la interfaz y documentación actual, SRT figuraba como la opción "Recomendado", induciendo a los usuarios a configuraciones problemáticas.
* **Solución Técnica:**
  - Remover la etiqueta "(Recomendado)" de SRT en `gui/static/i18n.js`, `gui/templates/index.html` y presets.
  - Designar a **UDP Unicast** como el protocolo estándar, recomendado y predeterminado para transmisiones en red local hacia OBS.
  - Presentar SRT como protocolo alternativo para enlaces a través de Internet o redes WAN con pérdida de paquetes.

### 2.6. Erradicación de Promesas Falsas de Latencia ("<100ms zerolatency")
* **Problema:**
  - Textos en la interfaz y presets prometían de forma engañosa "<100ms de zerolatency real sin buffers" o "~50ms en VLC".
* **Solución Técnica:**
  - Purgar todas las afirmaciones comerciales engañosas de `i18n.js`, `index.html` y documentación.
  - Reemplazar por explicaciones técnicas honestas: "Modo Zerolatency: Minimiza los buffers de codificación (VBV a 1.5 frames) y deshabilita el reordenamiento de fotogramas (B-frames = 0) para reducir el retardo de transmisión al mínimo físico posible del hardware".

---

## 3. Optimizaciones Tácticas del Sistema (Arquitectura Actual)

### 3.1. [P1.2] Estandarización a 60 FPS con Auto-Negociación Defensiva
- Configurar 60 FPS como el valor predeterminado global en `core/config_mgr.py`, `api/schemas.py`, presets y migración SQLite a versión 3.
- Si el sensor físico rechaza 60 FPS en DirectShow, conmutar defensivamente al framerate máximo admitido por la cámara (30 FPS) sin abortar la transmisión.

### 3.2. [P2.1] Pinning Automático a P-Cores en Windows NT
- En `core/process_optimizer.py`, implementar la función `get_pcore_affinity_mask()` utilizando `ctypes.windll.kernel32.GetLogicalProcessorInformationEx` con `RelationProcessorCore`.
- Identificar los núcleos con el mayor valor de `EfficiencyClass` (Performance Cores) y calcular la máscara de bits `core_mask`.
- En CPUs híbridas (Intel 12ª-15ª Gen, AMD con núcleos densos), aplicar la máscara tanto a los subprocesos FFmpeg como a MediaMTX. En CPUs homogéneas, asignar todos los núcleos lógicos.

### 3.3. Manejo Unificado de Privilegios Administrativos y UAC
- Evitar múltiples solicitudes de Control de Cuentas de Usuario (UAC) durante la ejecución.
- Solicitar elevación administrativa una única vez durante el inicio de la aplicación para que todos los procesos hijos (FFmpeg, MediaMTX, ajustes de prioridad y reglas de firewall) hereden el token administrativo sin interrumpir al usuario.

### 3.4. [P3.4] Lazy Startup y Apagado con Período de Gracia de MediaMTX
- Eliminar el inicio forzado de MediaMTX en `main.py`.
- Iniciar el servidor MediaMTX únicamente bajo demanda cuando:
  1. Se active al menos una cámara en protocolo SRT.
  2. El usuario abra una vista previa WebRTC (WHEP).
- Si no hay ningún flujo SRT ni visor WebRTC activo durante **20 segundos continuos** (período de gracia), apagar MediaMTX para liberar memoria RAM (~50 MB) y cerrar puertos de red (8889, 8890, 9997).

### 3.5. [P1.3] Bloqueo Inteligente de Auto-Exposición UVC (Anti-Drop FPS)
- Crear el módulo `core/uvc_control.py` interactuando con la interfaz DirectShow COM `IAMCameraControl` (`PROPSETID_VIDCAP_CAMERACONTROL`).
- Antes de iniciar la captura, fijar la exposición en modo manual (`CameraControl_Flags_Manual`) con un tiempo de obturación $\le 1/60\text{ s}$ para evitar caídas silenciosas a 15-20 FPS en penumbra.
- Incorporar degradación transparente: si la cámara no soporta `IAMCameraControl` o es virtual, continuar la transmisión sin interrumpir el flujo.

### 3.6. [P3.3] Optimización de Contenedor UDP Unicast y Protocolo Raw RTP
- En `core/command_builder.py`, afinar los parámetros de MPEG-TS para UDP Unicast:
  `-muxdelay 0 -muxpreload 0 -pat_period 0.1 -pcr_period 20 -flush_packets 1 -pes_payload_size 0`.
- Agregar soporte para el protocolo optativo `rtp` (Raw RTP) con autogeneración de archivo de sesión `.sdp` descargable desde la API para OBS Studio.

---

## 4. Matriz de Archivos Afectados en v2.8.3

| Archivo | Modificaciones Requeridas |
| :--- | :--- |
| `core/__version__.py` | Actualizar versión a `"2.8.3"`. |
| `pyproject.toml` | Actualizar versión a `"2.8.3"`. |
| `core/repository/database.py` | Migración de esquema SQLite a versión 3 (60 FPS default). |
| `core/config_mgr.py` | Presets y defaults actualizados a 60 FPS y protocolo UDP Unicast recomendado. |
| `core/stream_proc.py` | Corrección de URL de OBS (usar IP del receptor sin `@`), ajuste de caching VLC a 300 ms y remoción de `:clock-jitter=0`. |
| `core/command_builder.py` | Forzar MJPEG en 1080p para evitar caídas a 4:3, preservación de aspect ratio en reescalado y tuning MPEG-TS/RTP. |
| `core/process_optimizer.py` | Implementación de `get_pcore_affinity_mask()` con `GetLogicalProcessorInformationEx`. |
| `core/mediamtx_mgr.py` & `main.py` | Implementación de Lazy Startup y shutdown con período de gracia de 20s. |
| `core/uvc_control.py` | Nuevo módulo para bloqueo de auto-exposición UVC con `IAMCameraControl`. |
| `gui/static/app.js` | Corrección de payload en `confirmAndStartUnicast()` (enviar `protocol: 'udp', udp_mode: 'unicast'`), renderizado de IP de receptor sin `@`, actualización de caching VLC y textos. |
| `gui/static/i18n.js` | Remoción de "Recomendado" en SRT, eliminación de reclamos de "<100ms zerolatency", ajuste de textos en español e inglés. |
| `gui/templates/index.html` | Ajuste de etiquetas, banners informativos y formulario de configuración de cámaras. |
| `tests/test_audit_v283_features.py` | Suite de pruebas automatizadas validando cada una de las correcciones y nuevas funciones. |

---

## 5. PROMPT COMPLETO Y EJECUTABLE PARA IMPLEMENTAR LA v2.8.3

```markdown
### TASK: Implementación Completa de RTMS Versión 2.8.3

Trabajas sobre el repositorio RTMS ubicado en:
C:\Users\joaqu\.gemini\antigravity\worktrees\RTMS\split_version_upgrade_plan

Tu objetivo es implementar de manera exhaustiva, profesional y rigurosa la versión **2.8.3** de RTMS, manteniendo la arquitectura existente (Python 3.12, FastAPI, FFmpeg CLI, pywebview, DirectShow, MediaMTX) e implementando las siguientes correcciones de estabilidad y optimizaciones tácticas:

#### 1. Correcciones de Conexión, Red y OBS Studio
- **Sintaxis de URL para OBS**: En `core/stream_proc.py:187`, `gui/static/app.js:637, 2191` y en cualquier punto de generación de URLs para OBS, en modo UDP Unicast la URL debe ser `udp://<IP_RECEPTOR>:<PUERTO>` (o `udp://127.0.0.1:<PUERTO>` en loopback local). NUNCA usar la sintaxis `udp://@:puerto` para clientes OBS Unicast.
- **Persistencia de la IP del Receptor (`udp_host`)**: Corregir el bug crítico en `gui/static/app.js:1081` (`confirmAndStartUnicast()`) que enviaba `protocol: 'udp_unicast'`, provocando un error HTTP 422 de Pydantic y evitando que la IP se guardara. Debe enviar `protocol: 'udp'` y `udp_mode: 'unicast'`. Garantizar que al guardar, la IP se persista en SQLite y se muestre reactivamente en la tarjeta de la cámara.
- **Ajuste de Buffer para VLC**: En `core/stream_proc.py`, `app.js` y `vlc_playlist.xspf`, actualizar el `:network-caching` predeterminado a 300 ms (mínimo seguro 250 ms) y ELIMINAR por completo los modificadores `:clock-jitter=0 :clock-synchro=0` que provocan congelamientos en el reproductor VLC.
- **Degradar SRT y Designar UDP Unicast como Recomendado**: En `gui/static/i18n.js`, `gui/templates/index.html` y presets, quitar la etiqueta de "Recomendado" a SRT (debido a su inestabilidad y cuelgues con MediaMTX). Establecer UDP Unicast como el protocolo predeterminado y recomendado para redes locales.
- **Purgar Afirmaciones Falsas de Latencia**: Eliminar menciones a "<100ms de zerolatency" y promesas de 50ms en VLC en todos los archivos de interfaz, sustituyéndolas por explicaciones técnicas precisas sobre la supresión de buffers VBV y GOP ultracorto.

#### 2. Corrección de Aspect Ratio (Deformación 4:3 a 16:9 en 1080p)
- En `core/command_builder.py`, detectar cuando se configure resolución 1080p en webcams USB y solicitar prioritariamente compresión MJPEG (`-vcodec mjpeg`) para evitar que el controlador DirectShow rechace 1080p NV12 y caiga al modo por defecto en 640x480.
- Si se activa el reescalado defensivo (`dshow_options_failed`), reemplazar `-vf scale=W:H` plano por un filtro que preserve la relación de aspecto (`scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2:black`) para evitar deformaciones horizontales.

#### 3. Optimizaciones Tácticas de Sistema y Hardware
- **P1.2 Estandarización a 60 FPS**: Actualizar `config_mgr.py`, schemas Pydantic, presets y migración SQLite (versión 3) fijando 60 FPS por defecto, con fallback automático a 30 FPS si la cámara física rechaza 60 FPS.
- **P2.1 Pinning Automático a P-Cores**: En `core/process_optimizer.py`, implementar detección de topología de CPU con Win32 `GetLogicalProcessorInformationEx` (`RelationProcessorCore`, `EfficiencyClass`) para aislar P-Cores en CPUs híbridas e inyectar la máscara de afinidad en FFmpeg y MediaMTX; en CPUs homogéneas, mantener todos los núcleos.
- **UAC y Privilegios**: Asegurar manejo de elevación limpia al inicio para evitar carteles UAC repetitivos en runtime.
- **P3.4 Lazy Startup y Shutdown de MediaMTX**: Desacoplar el arranque de MediaMTX de `main.py`. Iniciar el proceso únicamente bajo demanda ante un stream SRT o una sesión WebRTC activa, y detenerlo tras un período de gracia de 20 segundos sin actividad.
- **P1.3 Bloqueo de Auto-Exposición UVC**: Crear `core/uvc_control.py` con `IAMCameraControl` en DirectShow COM para forzar obturación $\le 1/60\text{ s}$ en modo manual, previniendo caídas a 15-20 FPS en baja luz.
- **P3.3 Transporte UDP / RTP**: Calibrar flags de `mpegts` (`-muxdelay 0 -pes_payload_size 0 -flush_packets 1`) y soportar `rtp` optativo con autogeneración de archivo `.sdp`.

#### 4. Verificación y Calidad
- Actualizar la versión a `2.8.3` en `core/__version__.py` y `pyproject.toml`.
- Crear la suite de pruebas unitarias y de integración `tests/test_audit_v283_features.py` que valide cada una de estas características.
- Ejecutar linting con `ruff` y correr la suite de tests para asegurar 100% de aprobación sin regresiones.
```
