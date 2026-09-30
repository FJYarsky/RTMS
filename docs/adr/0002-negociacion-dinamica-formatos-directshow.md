# ADR-0002: Negociación Dinámica de Formatos DirectShow y Sondeo de Pines MJPEG

* **Fecha**: 2026-09-30
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Hardware / Silicio / DirectShow / Core
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
En sistemas multicámara con múltiples webcams conectadas por bus USB 2.0/3.0, el ancho de banda del controlador de host USB es el principal cuello de botella. En la versión 2.6.0 se introdujo la optimización de silicio USB para forzar la compresión interna del sensor mediante `-vcodec mjpeg`, reduciendo el tráfico en el bus en más de un 95%.

Sin embargo, en dispositivos de video físicos (como cámaras integradas de laptops, tarjetas capturadoras HDMI USB o webcams económicas) cuyos controladores DirectShow únicamente exponen pines en formatos no comprimidos nativos (`nv12`, `yuyv422`), forzar incondicionalmente `-vcodec mjpeg` causaba un fallo crítico fatal en FFmpeg:
```text
[in#0] Could not set video options
video=HD Webcam: I/O error (code 4294967291)
```
Esto provocaba que FFmpeg finalizara inmediatamente antes de inicializar la captura, dejando al usuario con el error de que el protocolo SRT no emitía video.

## 2. Factores Decisivos (Decision Drivers)
* **Compatibilidad Universal Plug & Play**: El sistema debe operar con cualquier cámara DirectShow sin requerir configuración manual por parte del usuario.
* **Preservación del Ancho de Banda USB**: Aprovechar al máximo la compresión MJPEG en el hardware del sensor siempre que esté disponible.
* **Prevención de Fallos Fatales de FFmpeg**: Nunca enviar argumentos de decodificación a DirectShow que el sensor no sea capaz de negociar en sus pines.
* **Rendimiento de Inicialización**: La detección del formato no debe retrasar el arranque del stream ni bloquear el bucle de eventos asíncrono.

## 3. Opciones Consideradas
* **Opción A (Parámetro manual en GUI)**: Obligar al usuario a marcar un checkbox "Usar MJPEG". Descartado por ser propenso a errores humanos y afectar negativamente la experiencia de usuario.
* **Opción B (Intentar MJPEG y capturar fallo de proceso)**: Iniciar FFmpeg con MJPEG, y si falla en los primeros segundos, reintentar con RAW. Descartado porque introduce un retardo perceptible (2-4 segundos de pantalla negra) y genera logs de error alarmantes.
* **Opción C (Sondeo dinámico previo de capacidades DirectShow con caché en memoria)**: Consultar los formatos soportados por el dispositivo mediante `ffmpeg -list_options true -f dshow -i video="..."` de forma previa y no bloqueante, almacenando el resultado en caché.

## 4. Decisión
Se implementa la **Opción C**:
1. En [`core/hardware.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/hardware.py) se crea la función `probe_device_mjpeg_support(raw_device: str) -> bool` que parsea de forma asíncrona la lista de formatos DirectShow (`pixel_format=mjpeg`).
2. En [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py) se evalúa `use_mjpeg_input`:
   - Si está configurado explícitamente por el usuario (`True`/`False`), se respeta dicha preferencia.
   - Si no está definido (modo automático), se consulta el caché del proceso o se dispara el sondeo dinámico.
   - Si el sensor soporta MJPEG, se inyecta `-vcodec mjpeg` y `rtbufsize=100M`.
   - Si no lo soporta (como la cámara `HD Webcam`), se omiten los argumentos MJPEG y se permite que DirectShow negocie `nv12` o `yuyv422` con `rtbufsize=65M`.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Resolución Definitiva del Fallo de SRT**: Las cámaras con pines `nv12`/`yuyv422` inician inmediatamente a 30 FPS sin rechazo de pines DirectShow.
* **Máxima Eficiencia USB Automática**: Las cámaras con soporte MJPEG continúan ahorrando ancho de banda en el bus sin intervención del usuario.
* **Zero-Lag**: El resultado se cachea en la instancia `StreamProcess`, por lo que los reinicios posteriores son instantáneos.

### Consecuencias Negativas / Limitaciones (-)
* En cámaras que únicamente soportan `yuyv422` sin compresión, varias cámaras en el mismo controlador USB 2.0 pueden saturar el bus si se utilizan simultáneamente en 1080p (documentado en [`docs/HARDWARE.md`](file:///C:/Users/joaqu/Desktop/RTMS/docs/HARDWARE.md)).

## 6. Validación y Cumplimiento
* Validado con hardware real físico (`HD Webcam`, USB vid_5986/pid_211b) transmitiendo a 30.67 FPS continuos con encoder NVENC.
* Pruebas automatizadas en [`tests/test_command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_command_builder.py) y en [`scripts/e2e_pipeline_tester.py`](file:///C:/Users/joaqu/Desktop/RTMS/scripts/e2e_pipeline_tester.py).
