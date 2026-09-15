# Matriz de Compatibilidad de Hardware y Encoders — RTMS v2.2.0

Este documento describe la matriz de compatibilidad validada de RTMS para captura de video DirectShow en Windows, codificación acelerada por hardware o CPU, y telemetría en tiempo real.

---

## 1. Codificadores Soportados

| Codificador | Fabricante | Requisitos Mínimos | Latencia Típica | Perfil Recomendado |
| :--- | :--- | :--- | :--- | :--- |
| **`h264_nvenc`** | NVIDIA | GeForce GTX 900+ / RTX / Quadro / Tesla | Ultra Baja (<15 ms encoder) | `preset=p1`, `tune=ull`, `delay=0` |
| **`h264_qsv`** | Intel | Core i3/i5/i7/i9 6ta Gen+ / Intel Arc | Muy Baja (<25 ms encoder) | `preset=veryfast` |
| **`h264_amf`** | AMD | Radeon RX 400+ / Vega / RDNA | Baja (<30 ms encoder) | `quality=speed`, `usage=ultralowlatency` |
| **`libx264`** | CPU | Cualquier procesador x86_64 | Variable según núcleos | `preset=ultrafast`, `tune=zerolatency` |

> [!NOTE]
> **Autodetección y Telemetría en Vivo de GPU**: Al iniciar cada stream en modo `"auto"`, RTMS efectúa una prueba de inicialización con un lienzo de resolución estándar (`640x360`). Si la GPU no responde o carece de memoria VRAM disponible, el sistema conmuta automáticamente y sin interrupción humana al modo CPU (`libx264`). Además, el motor de telemetría HUD consulta en tiempo real mediante NVML directo (`nvml.dll`) el porcentaje de utilización y consumo de VRAM de la GPU.

---

## 2. Resoluciones, Tasas de Cuadros y Bitrates Recomendados

| Resolución | Aspect Ratio | FPS | Bitrate Recomendado | Bitrate Máximo | Protocolo Sugerido |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **480p** | 16:9 | 24 / 30 | 1,500 kbps | 2,000 kbps | SRT / UDP |
| **720p** | 16:9 | 30 / 60 | 3,000 kbps | 4,500 kbps | SRT (Baja Latencia) |
| **1080p** | 16:9 | 30 / 60 | 6,000 kbps | 8,000 kbps | SRT (Broadcast) |
| **1440p** | 16:9 | 30 / 60 | 10,000 kbps | 14,000 kbps | SRT |
| **4K** | 16:9 | 30 | 18,000 kbps | 25,000 kbps | SRT (NVENC / QSV) |

---

## 3. Dispositivos de Captura DirectShow

### Cámaras Físicas Validadas
- **Cámaras Web USB**: Logitech C920, C922, Brio 4K, StreamCam, Razer Kiyo, Anker PowerConf.
- **Capturadoras HDMI USB/PCIe**: Elgato Cam Link 4K, HD60 S+, HD60 X, AVerMedia Live Gamer MINI/Ultra, Blackmagic Intensity Pro.
- **Cámaras Integradas**: Laptops Dell, Lenovo, HP, Asus con sensores UVC DirectShow.

### Dispositivos Virtuales / Software
RTMS detecta automáticamente cámaras virtuales y las clasifica (`is_virtual: true`, `auto_start: false`) para evitar colisiones de recursos o consumo innecesario de Tensor Cores y GPU en reposo:
- NVIDIA Broadcast (Cámara de IA con reducción de ruido y fondo virtual)
- OBS Virtual Camera
- Elgato Virtual Camera
- vMix Video
- Unity Video Capture
- DroidCam / Iriun Webcam / ManyCam / SplitCam / NDI Video

<!-- RTMS Hardware Compatibility Reference v2.2.0 -->
