# RTMS v2.8.0 — Streaming de Video Puro de Baja Latencia, Calibración Inteligente SRT/VLC, Rediseño UI Obsidian y Validación Integral

**Fecha:** 27 de Septiembre de 2026 | **Versión:** `v2.8.0`

[![Descargar RTMS v2.8.0](https://img.shields.io/badge/%E2%AC%87%EF%B8%8F%20Descargar%20RTMS-v2.8.0%20(Windows%20x64)-00E5FF?style=for-the-badge&logo=windows&logoColor=050b14)](https://github.com/FJYarsky/RTMS/releases/latest)

---

### 🎥 Política Estricta de Video Puro y Latencia Optimizada Sub-100ms
- **Bandera Mandataria `-an`**: Inyección sistemática de `-an` en todas las tuberías de captura, transcodificación y preview de FFmpeg. Se desactiva cualquier captura de audio DirectShow, transcodificación de pistas de audio y grabación ISO, dedicando el 100% de la capacidad de cómputo al streaming de video en vivo.
- **Cadencia GOP=15 y Sintonización de Bajo Retardo**: Configuración estricta de grupo de imágenes en 15 fotogramas (250-500 ms) junto con `-fflags nobuffer+flush_packets -flags low_delay`, garantizando un tiempo de sincronización inmediato en reproductores sin búfer de acumulación.
- **Calibración VBV al 35%**: Ajuste fino del búfer de tasa de bits (`bufk = int(bitrate * 0.35)k`) previniendo el estrangulamiento de bits en fotogramas complejos y erradicando micro-cortes.

---

### 🧪 Calibración Inteligente SRT y Reproducción VLC Fluida
- **Desactivación Contextual de Búfer SRT**: Cuando se activa el modo `zerolatency`, el selector manual de latencia SRT se oculta y calibra automáticamente a 50 ms con un badge explicativo, eliminando inconsistencias operativas.
- **Comando VLC Optimizado**: Ajuste de `:network-caching=150` y eliminación de flags de descarte agresivo, logrando streaming continuo a 60 FPS sin congelamientos de fotograma.
- **Limpieza de Opciones Obsoletas**: Eliminación de opciones no funcionales de lanzamiento directo en VLC y listas XSPF en el diálogo de conexión.

---

### 🎨 Rediseño Visual Obsidian Dark Glassmorphism y Sección Dispositivos
- **Nueva Sección Dispositivos y Flujos**: Tarjetas modernas estilo dashboard con avatar visual de cámara, especificaciones técnicas compactas (resolución, FPS objetivo, códec, acelerador HW), HUD de telemetría en vivo (FPS actuales, bitrate, uptime) y conmutador de autostart integrado.
- **Barra de Resumen de Flujos**: Métricas globales en tiempo real con conteo de cámaras totales, en vivo, detenidas y virtuales.
- **Menú Superior Simplificado**: Traslado de las herramientas de diagnóstico de latencia y ping a Configuración del Sistema, depuración del selector de idiomas (ES/EN) y botón de compartir limpio.
- **Superficies Translúcidas y Contraste WCAG AAA**: Fondo obsidiana profundo (`#070b14`), efectos de desenfoque de fondo y acentos lumínicos cian y azul celeste.

---

### 🌐 Bilingüismo 100% Estricto (Español Argentina / Inglés Estados Unidos)
- **Eliminación Total de Textos Mixtos**: 100% Español argentino cuando se selecciona `es`, 100% Inglés estadounidense cuando se selecciona `en`.
- **Diccionarios Simétricos Dinámicos**: Traducción integral del DOM incluyendo elementos de formulario, tooltips de navegación y alertas contextuales.
- **Conmutación en Caliente**: Re-renderizado instantáneo del panel sin recarga de página.

---

### 🇦🇷 Acreditación e Identidad Nacional
- **Mapa-Bandera Oficial de las Islas Malvinas**: Inclusión del archivo SVG vectorial auténtico de Wikimedia Commons en el modal "Acerca de RTMS".
- **Insignia Soberana**: "Hecho en Argentina • Las Malvinas son argentinas".

---

### ⚡ Aceleración por Hardware HEVC y AV1
- **Soporte Ampliado**: Detección y priorización automática de codificadores NVIDIA NVENC HEVC, Intel QuickSync HEVC, AMD AMF HEVC, libx265 CPU y perfiles AV1.

---

### 🛡️ Calidad de Código, Fuzzing y Estrés
- **345 Pruebas Automatizadas Pasando**: 100% de éxito en suites unitarias, de integración, concurrencia, límites, fuzzing y benchmarking, con cobertura de código integral.
- **Auditoría Visual y Capturas Reales**: 11 capturas de pantalla de alta resolución integradas en la documentación y README demostrando la interfaz real en funcionamiento.

