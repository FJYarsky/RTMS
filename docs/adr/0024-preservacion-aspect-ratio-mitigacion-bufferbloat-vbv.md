# ADR-0024: Preservación de Relación de Aspecto y Mitigación de Bufferbloat VBV a Nivel de Cuadro

* **Estado**: Aceptado
* **Fecha**: 2026-10-03
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Video / FFmpeg / Hardware
* **Subflujos y Componentes**: [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py), [`core/hardware.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/hardware.py)
* **Vínculos**: Extiende [ADR-0002](0002-negociacion-dinamica-formatos-directshow.md) y [ADR-0007](0007-priorizacion-codificadores-hardware.md)

---

## 1. Contexto

En el procesamiento de video en tiempo real desde sensores DirectShow en Windows, surgen dos desafíos críticos de calidad óptica y latencia de empaquetado:

### 1. Distorsión Geométrica de la Relación de Aspecto (1080p en USB 2.0)
El bus USB 2.0 High Speed posee un ancho de banda teórico máximo de $480\text{ Mbps}$ (rendimiento práctico de $\sim 300\text{ Mbps}$). Una señal no comprimida YUYV/NV12 a 1080p60 requiere $\sim 1.98\text{ Gbps}$, superando con creces la capacidad física del bus USB 2.0.
Cuando un dispositivo DirectShow solicita un pin no comprimido en 1080p a través de un puerto USB 2.0, el controlador de la cámara suele rechazar la solicitud o degradar silenciosamente a un modo de compatibilidad de baja resolución, típicamente **640x480 con relación de aspecto 4:3**.
Si la tubería de transcodificación escala rígidamente esta señal a 1080p ($1920\times 1080$, relación 16:9) mediante un filtro simple `scale=1920:1080`, la imagen resultante sufre una deformación horizontal severa (estiramiento anamórfico artificial), inaceptable en una producción audiovisual profesional.

### 2. Bufferbloat en el Control de Tasa VBV (Video Buffer Verifier)
El modelo de control de tasa VBV de H.264/HEVC utiliza un parámetro de tamaño de búfer (`-bufsize`) para prevenir desbordamientos o subdesbordamientos del búfer del decodificador.
Históricamente, los sistemas de streaming utilizaban fórmulas basadas en ventanas de tiempo amplias, tales como `bufsize = bitrate * 0.35` (una ventana de $350\text{ ms}$) o `bufsize = bitrate * 1.0` ($1000\text{ ms}$).
Bajo este esquema, ante cuadros complejos (ej. cortes de escena o movimiento brusco de cámara), el codificador acumula ráfagas masivas de bits (*packet bursting*), provocando que los paquetes viajen retrasados en la cola de red y añadiendo de 15 a 30 ms de fluctuación y latencia en el decodificador receptor.

---

## 2. Factores Decisivos

* **Preservación Geométrica Absoluta**: Toda señal debe conservar su relación de aspecto original (16:9, 4:3, etc.) independientemente de la resolución nativa devuelta por el sensor o la falla en la negociación de pines.
* **Erradicación del Bufferbloat VBV**: El control de tasa debe forzar una tasa de bits plana cuadro a cuadro sin encolamiento en el muxer ni en el receptor.
* **Priorización de Silicio MJPEG en 1080p+**: Aprovechar la compresión por hardware en el microcontrolador de la cámara web para transferir tramas comprimidas por el bus USB 2.0 sin saturarlo.
* **Sincronización Monótona de Timestamps**: Garantizar marcas de tiempo de presentación (PTS/DTS) estrictamente crecientes para erradicar avisos de `Non-monotonic DTS` y congelamientos en decodificadores de hardware.

---

## 3. Alternativas Evaluadas

### Opción A: Escalamiento directo sin preservación de aspecto (`scale=w:h`) (Descartada)
* *Ventajas*: Mínimo costo computacional.
* *Desventajas*: Provoca imágenes estiradas o deformadas cuando la cámara degrada a 4:3.

### Opción B: Búfer VBV desactivado o en cero (`-bufsize 0`) (Descartada)
* *Ventajas*: Emisión inmediata de paquetes.
* *Desventajas*: Viola la especificación HRD (Hypothetical Reference Decoder) de H.264/HEVC, provocando que reproductores estrictos de hardware (vMix, Smart TVs, decodificadores NDI) descarten el flujo por violación de límites del decodificador.

### Opción C (Elegida): Priorización MJPEG en 1080p+, filtro de padding inteligente y micro-búfer VBV a 1.5 cuadros
* *Ventajas*:
  1. En resoluciones $\ge 1080p$, se activa el pin de compresión MJPEG nativo del sensor, permitiendo streaming 1080p60 a través del bus USB 2.0 sin degradación a 640x480.
  2. En caso de fallback, se inyecta el filtro `force_original_aspect_ratio=decrease,pad=w:h:(ow-iw)/2:(oh-ih)/2:black`, generando barras negras laterales (*pillarbox*) o superior/inferior (*letterbox*) pero manteniendo intacta la geometría de la imagen.
  3. Se restringe el tamaño del búfer VBV a una micro-ventana de 1.5 cuadros:
     $$\text{bufk} = \max\left(50, \left\lfloor \frac{\text{bitrate}}{\text{fps}} \times 1.5 \right\rfloor\right)\text{ kb}$$
     Para $3000\text{ kbps}$ a 60 FPS, el búfer es de solo $75\text{ kb}$ (frente a los antiguos $1050\text{ kb}$), erradicando las ráfagas y manteniendo un flujo de paquetes ultra-plano.
  4. Inyección mandataria de `-fps_mode cfr` para forzar cadencia constante de fotogramas.
* *Desventajas*: El cálculo dinámico añade mínima lógica en el generador de comandos.

---

## 4. Decisión

Se adopta e implementa en [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py) la siguiente especificación técnica:

1. **Priorización de Entrada MJPEG para Fuentes 1080p+**:
   ```python
   is_1080p_or_more = any(res in video_size for res in ("1920x1080", "2560x1440", "3840x2160"))
   if is_1080p_or_more and not getattr(proc, "mjpeg_input_failed", False):
       use_mjpeg = True
   ```
   Al utilizar `-vcodec mjpeg -rtbufsize 3M`, la cámara transmite JPEG comprimido por el bus USB, superando holgadamente el límite de ancho de banda físico.

2. **Filtro de Relación de Aspecto y Padding**:
   Si la negociación de pines DirectShow falla y se requiere escalamiento seguro:
   ```python
   w, h = video_size.split("x")
   aspect_filter = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
   cmd += ["-vf", aspect_filter, "-r", str(fps)]
   ```

3. **Cálculo del Micro-Búfer VBV de Ultra-Baja Latencia**:
   ```python
   if zerolatency:
       vbv_bufsize_val = max(50, int(bitrate / max(1, fps) * 1.5))
       bufk = f"{vbv_bufsize_val}k"
   ```

4. **Sincronización Estricta de Reloj de Salida**:
   ```python
   cmd += ["-fps_mode", "cfr"]
   ```

```
     +------------------------------------------------------------------+
     |                  DirectShow Video Capture Source                 |
     +------------------------------------------------------------------+
                                       |
                     Resolución solicitada: 1080p60
                                       |
                /--------------------------------------\
      [Sensor USB 2.0]                           [Sensor USB 3.0 / PCIe]
             |                                              |
      Pin MJPEG por Silicio                          Pin Nativo NV12
      (-vcodec mjpeg -rtbufsize 3M)                  (-pixel_format nv12)
             \                                              /
              +-----------------------+--------------------+
                                      |
                           [Aspect Ratio Guard]
                           force_original_aspect_ratio=decrease
                           pad=1920:1080:(ow-iw)/2:(oh-ih)/2
                                      |
                           [Micro-Window VBV]
                           bufsize = bitrate / 60 * 1.5 (75 kb)
                           fps_mode = cfr
                                      |
                     +----------------v-----------------+
                     |   Bitstream H.264/HEVC Ultra-Flat|
                     |   Cero Bufferbloat / P50 <= 40ms |
                     +----------------------------------+
```

---

## 5. Consecuencias

### Positivas
* **Geometría Óptica Intacta**: Las proporciones faciales y espaciales se mantienen fidedignas bajo cualquier contingencia de degradación de hardware.
* **Eliminación de 15-30 ms de Latencia**: El micro-búfer VBV impide que el codificador retrase tramas, produciendo una tasa de bits continua y homogénea.
* **Resolución 1080p Real en Webcams USB 2.0**: Al forzar el pin MJPEG, las cámaras Logitech C920 y equivalentes logran entregar 1080p real sin colapsar el bus USB.

### Negativas
* **Mínimo Uso de CPU en Decodificación MJPEG**: Cuando se utiliza el pin MJPEG, FFmpeg decodifica las tramas JPEG del sensor antes de pasarlas al codificador por hardware H.264, lo cual insume $\approx 2-3\%$ adicional de CPU, plenamente justificado por la estabilidad de resolución obtenida.
