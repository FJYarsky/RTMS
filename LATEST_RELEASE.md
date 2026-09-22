# RTMS v2.5.2 — Optimización de Latencia Extrema en SRT/UDP, Soporte UDP Unicast/Multicast, Códigos QR Offline y Aceleración de Arranque

**Fecha:** 22 de Septiembre de 2026 | **Versión:** `v2.5.2`

---

### 🚀 Optimización de Latencia Extrema en SRT y UDP (VLC Media Player, OBS)
- **Modos UDP Unicast y Multicast**:
  - Soporte explícito para UDP Unicast (`udp_unicast`, por defecto a `127.0.0.1` o IP destino específica) para enlaces directos locales, y UDP Multicast (`udp_multicast`, grupo `239.255.0.X`) para distribución en red de área local (LAN).
  - Formato MRL canónico para VLC: `udp://@<ip>:<port>` sin parámetros de consulta query (`?pkt_size`), garantizando reconocimiento inmediato del analizador de red de VLC.
  - Comprobado en decodificación dummy en tiempo real de VLC con cero pérdida de paquetes y retardo inferior a 80 ms.
- **Reducción Drástica de Retardo en SRT**:
  - Eliminado `smoother=live` en publicaciones caller hacia MediaMTX, suprimiendo esperas de pacing innecesarias en tráfico de loopback local.
  - Fijación de GOP a 1 segundo (`gop = fps` en modo zerolatency), asegurando llegada continua de paquetes IDR/SPS/PPS para enganche de reproducción instantáneo (<100 ms).
  - Parámetros de multiplexión MPEG-TS optimizados: `-pat_period 0.1 -pcr_period 20` para sincronización ultrarrápida de reloj y demuxing.

---

### 📱 Códigos QR Offline para Conexión Móvil en VLC
- **Integración Autónoma sin Dependencias de Internet**:
  - Biblioteca `qrcode.min.js` empaquetada localmente (100% offline, sin llamadas externas a CDN).
  - Generación dinámica de código QR accesible con un clic desde las tarjetas de cámara y desde la vista de conexión universal OBS/VLC.
  - Permite a cámaras de control, directores de escena y operadores en smartphones/tablets apuntar la cámara de su dispositivo y abrir el stream al instante en VLC Mobile (iOS/Android).
  - Incluye botón de copiado directo al portapapeles y guía paso a paso de uso en VLC para móviles.

---

### ⚡ Arranque Instantáneo y Prevención de Diálogos UAC / Administrador
- **Desbloqueo Automático de Binarios Windows**:
  - Función `unblock_app_binaries` para eliminar flujos alternativos NTFS (`Zone.Identifier`) en `ffmpeg.exe`, `ffplay.exe` y `mediamtx.exe`.
- **Reglas Asíncronas de Firewall de Windows**:
  - Creación y verificación de reglas para `mediamtx.exe` ejecutadas en segundo plano (`asyncio.to_thread`) sin bloquear la apertura de la ventana de WebView2 (<1 segundo).
- **Temporizador Multimedia de Alta Precisión**:
  - Llamada a `timeBeginPeriod(1)` en Windows para asegurar resolución de reloj de 1 ms en el planificador de hilos, reduciendo el jitter de streaming.
- **Prioridad de Proceso para FFmpeg**:
  - Asignación de `ABOVE_NORMAL_PRIORITY_CLASS` (0x00008000) a los procesos de captura y codificación para evitar caídas de cuadros ante picos de uso del sistema.

---

### 👁️ Monitores de Vista Previa Instantáneos y Confiables
- **Inicialización de Latencia Cero**:
  - Parámetros `-probesize 100k -analyzeduration 500k -fflags nobuffer+flush_packets -flags low_delay` en flujos MJPEG y visores FFplay, abriendo la previsualización en menos de 200 ms.
  - Detección y generación virtual (`lavfi testsrc2`) para cámaras virtuales y estados inactivos, evitando excepciones en el demuxer DirectShow de Windows.

---

### 🎨 Refinamiento Estético y Consistencia Visual
- Corrección del diseño y estilos en el campo de entrada de puerto MediaMTX en el modal de Ajustes Generales (`form-ctrl`, fondo oscuro y borde unificado).
- Realineación geométrica del encabezado y badge de estado en el modal de vista previa.

---

### 🧪 Calidad, Verificación y Suite de Pruebas
- Suite completa de 155 pruebas automatizadas (150 aprobadas, 5 omitidas de hardware físico).
- Linters y formateador `ruff` validados sin advertencias.
- Catálogo canónico de GitHub preservado en 32/32 elementos raíz (`scripts/manage_descriptions.py --check`).
