# Manual de Operaciones y Runbook de Producción (Ops Runbook)

* **Versión del Sistema**: RTMS v2.8.0+
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Operaciones / Compilación / Kernel Tuning / Benchmarking / Troubleshooting

---

## 1. Directrices de Compilación y Empaquetado Portable

RTMS se distribuye como una aplicación de Windows x64 autónoma y portable (Zero-Install), que integra el entorno de Python, dependencias nativas y los binarios de medios (`ffmpeg.exe`, `mediamtx.exe`, `ffplay.exe`).

### 1.1 Script de Construcción (`build_portable.bat`)
Para compilar la versión de distribución oficial:

```cmd
:: 1. Activar entorno virtual con dependencias bloqueadas
uv sync --locked

:: 2. Ejecutar script maestro de empaquetado
build_portable.bat
```

### 1.2 Parámetros Críticos de PyInstaller
El empaquetado se rige por las siguientes banderas arquitectónicas:
* `--noconsole`: Oculta la ventana de comandos negra de Windows. En runtime, `main.py` redirige `sys.stdout` y `sys.stderr` a `_NullWriter` para evitar excepciones `NoneType.write()` en entornos GUI.
* `--add-data "gui;gui"`: Incluye plantillas HTML5, estilos CSS3, scripts JS y recursos vectoriales de marca (`brand_assets_sheet.png`, logos).
* `--add-data "bin;bin"`: Embebe los ejecutables binarios estáticos de 64 bits (`ffmpeg.exe`, `mediamtx.exe`, `ffplay.exe`).
* `--icon "icon.ico"`: Asigna el imagotipo de alta resolución al ejecutable compilado.
* `rtms.exe.config`: Manifiesto .NET/Win32 con flags DPI-Aware (`PerMonitorV2`) y compatibilidad para Windows 10/11.

---

## 2. Afinamiento del Entorno Windows y Kernel Tuning

Para garantizar latencias estables por debajo de 100 ms y evitar la pérdida de cuadros en producciones continuas de más de 8 horas, se aplican las siguientes directivas de optimización del sistema:

### 2.1 Calibración del Reloj del Sistema Operativo (1 ms Timer Resolution)
Por defecto, Windows utiliza un tick de reloj de 15.6 ms. RTMS eleva automáticamente la frecuencia a 1 ms en su arranque mediante la API multimedia:
```python
winmm = ctypes.windll.winmm
winmm.timeBeginPeriod(1)  # Inyectado al iniciar el servicio
winmm.timeEndPeriod(1)  # Restaurado al finalizar la sesión
```
Esto reduce la desviación estándar (*jitter*) en la temporización de cuadros de video a menos de 0.8 ms.

### 2.2 Desactivación de Ahorro Energético en Adaptadores de Red (PnPCapabilities = 24)
Para evitar micro-cortes y fluctuaciones en sockets SRT/UDP, se desactiva el ahorro de energía en todas las tarjetas de red físicas directamente mediante la manipulación del registro de Windows:
```cmd
:: Clave de Registro:
HKLM\SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}\<DeviceIndex>
:: Valor fijado:
PnPCapabilities = 0x00000018 (24 decimal)
```
*Nota*: Realizado de forma nativa por `core/power_mgr.py` sin utilizar scripts PowerShell para evitar alertas en antivirus.

### 2.3 Reglas del Firewall de Windows (Zero-Prompt Setup)
RTMS provisiona automáticamente las reglas requeridas en Windows Defender Firewall para permitir el tráfico de video en red local:
```cmd
netsh advfirewall firewall add rule name="RTMS API" dir=in action=allow protocol=TCP localport=8000-8099
netsh advfirewall firewall add rule name="RTMS Streaming" dir=in action=allow protocol=UDP localport=8890,9000-9200
netsh advfirewall firewall add rule name="RTMS MediaMTX" dir=in action=allow program="%BASE_DIR%\bin\mediamtx.exe" enable=yes
```

---

## 3. Procedimientos de Profiling, Benchmarking y Medición de Ping Óptico

RTMS incluye una suite de certificación matemática de latencia de extremo a extremo que no depende de sensores externos ni de OCR.

### 3.1 Verificación Integral Automatizada
Ejecute la suite completa de pruebas de la cadena de ejecución:
```cmd
python scripts/e2e_pipeline_tester.py --all
```

### 3.2 Benchmark Óptico de Ping y Jitter Sub-milisegundo
Para medir la latencia exacta introducida por el pipeline de captura, codificación, conmutación en MediaMTX y decodificación:

```cmd
python scripts/verify_ultra_low_latency_pipeline.py --duration 10 --port 9050
```

**Métricas Reportadas**:
* **Ping Mínimo / Máximo / Promedio**: Medido muestreando los centroides de la cabecera Barker de 72 bits grabada cuadro a cuadro.
* **Jitter ($J$)**: Desviación estándar de los tiempos de llegada de paquetes.
* **Cuadros Perdidos (*Dropped Frames*)**: Saltos detectados en el contador secuencial de 16 bits.
* **Cuadros Duplicados (*Stutter / Freezes*)**: Detección de timestamps estancados con reloj de sistema avanzando.

**Criterio de Aceptación de Grado de Producción**:
* Ping Promedio $\le 100$ ms.
* Jitter $\le 15$ ms.
* Cuadros Perdidos $= 0\%$ en red local cableada Gigabit.

---

## 4. Guía de Resolución de Incidentes Críticos (Troubleshooting Runbook)

### Incidente 1: Rechazo de Pines DirectShow (`I/O error code 4294967291`)
* **Síntoma**: Al iniciar una cámara en el dashboard, transiciona a estado `ERROR` y el log muestra:
  `[in#0] Could not set video options: video=...: I/O error (code 4294967291)`.
* **Causa Raíz**: El sensor de video o capturadora HDMI no admite compresión interna MJPEG en sus pines DirectShow (solo entrega formatos no comprimidos `yuyv422` o `nv12`).
* **Procedimiento de Resolución**:
  1. Abrir la configuración de la cámara en el Dashboard (`⚙️`).
  2. Verificar que `Negociación Dinámica DirectShow` esté en modo Automático (ADR-0002).
  3. Si el dispositivo persiste en fallo, desmarcar la opción `Forzar MJPEG` para que el sistema solicite entrada cruda `pixel_format=yuyv422` con buffer ampliado `rtbufsize=65M`.

---

### Incidente 2: Colisión de Puertos o Sockets Bloqueados (`WSAEADDRINUSE / WinError 10048`)
* **Síntoma**: Error al iniciar MediaMTX en el puerto 8890 o fallo al arrancar transmisiones SRT.
* **Causa Raíz**: Un proceso externo o una instancia huérfana de una versión antigua no blindada retiene el socket.
* **Procedimiento de Resolución**:
  1. Identificar el proceso ocupando el puerto:
     ```cmd
     netstat -ano | findstr :8890
     netstat -ano | findstr :8000
     ```
  2. Si el proceso no es el RTMS activo, liquidarlo por PID:
     ```cmd
     taskkill /F /PID <PID>
     ```
  3. En RTMS v2.8.0+, el gestor `PortManager` reasigna automáticamente el flujo al siguiente puerto disponible (`reallocate_if_collided`). Reiniciar el flujo desde la interfaz web.

---

### Incidente 3: Latencia Acumulada o Rechazo `ERROR:ROGUE` en SRT
* **Síntoma**: El video en OBS Studio presenta un retraso incremental de varios segundos, o MediaMTX registra en logs `gosrt: ERROR:ROGUE`.
* **Causa Raíz**: El emisor no está descartando paquetes atrasados o el parámetro de suavizado (*smoother*) está introduciendo retardo artificial.
* **Procedimiento de Resolución**:
  1. Verificar que la URL de publicación contenga incondicionalmente `tlpktdrop=1` (garantizado en `StreamProc`).
  2. Asegurarse de que `smoother=live` esté desactivado en modo caller.
  3. En OBS Studio, en la fuente multimedia SRT, añadir la cadena de latencia calibrada:
     `srt://127.0.0.1:8890?streamid=read:{cam_id}&latency=50000&rcvbuf=65536&tlpktdrop=1`

---

### Incidente 4: Congelamiento o Pantalla Negra en Reproductores VLC
* **Síntoma**: VLC Media Player muestra pantalla negra o tarda más de 5 segundos en reproducir la señal UDP.
* **Causa Raíz**: El buffer de red predeterminado de VLC (1000 ms) desincroniza el reloj frente al flujo en tiempo real de RTMS.
* **Procedimiento de Resolución**:
  1. No abrir la URL directamente con doble clic simple en VLC sin argumentos.
  2. Utilizar el comando generado por RTMS con parámetros de baja latencia:
     ```cmd
     vlc.exe "udp://@239.255.0.1:9000" :network-caching=50 :clock-jitter=0 :clock-synchro=0
     ```
  3. Alternativamente, utilizar el botón `Abrir en VLC` del Dashboard, el cual genera y ejecuta automáticamente un archivo de lista de reproducción `.xspf` con las directivas de caching precargadas.

---

### Incidente 5: Fallo de GPU NVENC por Límite de Sesiones Concurrentes
* **Síntoma**: Al encender la cuarta o quinta cámara, la transmisión falla con `Cannot open video encoder: No available sessions`.
* **Causa Raíz**: Las tarjetas gráficas NVIDIA de la línea GeForce tienen un límite de hardware impuesto por el controlador (habitualmente 3 a 5 sesiones simultáneas de codificación NVENC).
* **Procedimiento de Resolución**:
  1. RTMS detecta automáticamente el código de error `ENCODER` en la máquina de estados.
  2. El supervisor watchdog degrada automáticamente dicho flujo a CPU con `libx264 -preset ultrafast -tune zerolatency` (`force_cpu=True`) conforme a ADR-0007.
  3. En la interfaz web, el indicador de la cámara mostrará la insignia de advertencia amarilla `CPU Fallback`, garantizando que la emisión nunca se interrumpa.
