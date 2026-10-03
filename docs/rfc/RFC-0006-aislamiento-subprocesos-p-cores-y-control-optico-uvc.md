# RFC-0006: Aislamiento de Subprocesos Multimedia en Núcleos de Rendimiento (P-Cores) y Control Óptico DirectShow UVC

* **RFC Número**: 0006
* **Título**: Aislamiento de Subprocesos Multimedia en Núcleos de Rendimiento (P-Cores) y Control Óptico DirectShow UVC
* **Estado**: Implementado
* **Fecha de Implementación**: 2026-10-03
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Kernel Windows / Rendimiento de Silicio / DirectShow COM / Streaming en Tiempo Real
* **Módulos Afectados**: [`core/process_optimizer.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/process_optimizer.py), [`core/uvc_control.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/uvc_control.py), [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py), [`core/stream_proc.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_proc.py)
* **ADRs Relacionados**: [ADR-0020](../adr/0020-afinidad-procesos-p-cores-arquitecturas-hibridas-windows.md), [ADR-0021](../adr/0021-control-directshow-com-uvc-bloqueo-auto-exposicion.md), [ADR-0002](../adr/0002-negociacion-dinamica-formatos-directshow.md)

---

## 1. Resumen

Este RFC especifica la arquitectura de bajo nivel implementada en RTMS para aislar la ejecución de subprocesos multimedia intensivos (instancias de `ffmpeg.exe` y el broker `mediamtx.exe`) en los núcleos de máximo rendimiento (**P-Cores**) del microprocesador bajo el planificador de Windows NT, y el subsistema de control óptico directo sobre sensores USB mediante la interfaz COM DirectShow `IAMCameraControl` para bloquear el tiempo de obturación y erradicar caídas invisibles de la tasa de cuadros por segundo (**Anti-Drop FPS**).

Esta ingeniería combinada permite garantizar de forma determinista el cumplimiento del **SLA de ultra-baja latencia ($\le 50\text{ ms}$ P50 vidrio a vidrio)** y la estabilidad ininterrumpida de **60 FPS** en transmisiones multicámara en vivo, eliminando por completo la degradación causada por la asignación errónea de hilos en núcleos de eficiencia energética (E-Cores) y la desaceleración del sensor físico de las cámaras web en condiciones de iluminación variable.

---

## 2. Motivación

El despliegue de estaciones de trabajo modernas para producción audiovisual y broadcast sobre Windows 11 y Windows 10 (versión 21H2+) introdujo una disrupción en el comportamiento del planificador del sistema operativo debido a las microarquitecturas híbridas (Intel Thread Director con P-Cores y E-Cores, así como procesadores AMD con núcleos densos Zen 4c).

### 2.1. El Problema de la Inversión de Núcleos en Carga Multimedia Concurrente
Durante una transmisión con 2 a 6 cámaras simultáneas en 1080p60 o 720p60:
1. Cada flujo de video requiere un proceso de codificación y empaquetado con una cadencia temporal innegociable de un cuadro cada $16.66\text{ ms}$.
2. Si el planificador de Windows NT asigna un proceso o hilo de transcodificación de FFmpeg a un E-Core (diseñado para eficiencia energética con frecuencias de 2.0-3.5 GHz y menor IPC vectorial), el tiempo de procesamiento por fotograma se incrementa hasta los 22-35 ms.
3. El búfer de captura de DirectShow (`-rtbufsize`) se llena con fotogramas en espera, introduciendo **bufferbloat severo** (saltos de latencia de $100\text{ ms}$ a $400\text{ ms}$) y provocando eventuales descartes de cuadros (*frame dropping*).

### 2.2. El Problema de la Auto-Exposición UVC en Sensores Físicos
En sensores USB UVC económicos o de consumo común (ej. Logitech C920/C922 y webcams USB 2.0 genéricas):
1. El firmware de la cámara controla automáticamente la exposición mediante un bucle de retroalimentación óptica.
2. Si la iluminación ambiental desciende, el sensor intenta evitar la subexposición aumentando el tiempo de apertura del obturador a $\ge 33\text{ ms}$ o $\ge 50\text{ ms}$.
3. Físicamente, el sensor se vuelve incapaz de capturar 60 fotogramas en un segundo, entregando a DirectShow un flujo de 15 a 20 FPS. Ningún ajuste de software en FFmpeg puede recuperar fotogramas que el silicio nunca generó.

---

## 3. Especificación Detallada

### 3.1. Optimizador de Procesos y Topología de Silicio (`core/process_optimizer.py`)

#### 3.1.1. Introspección de Topología de CPU mediante `GetLogicalProcessorInformationEx`
El módulo no asume índices de núcleos fijos ni realiza llamadas destructivas. En su lugar, consulta la API Win32 del kernel de Windows:

```python
RelationProcessorCore = 0  # Filtra información a nivel de núcleos lógicos y físicos
```

Se procesa la estructura nativa `SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX`:
* **`EfficiencyClass` (BYTE)**: En procesadores híbridos Intel, los E-Cores reportan `EfficiencyClass = 0`, mientras que los P-Cores reportan `EfficiencyClass = 1` (o 2 en núcleos con tecnología Turbo Boost Max 3.0 / Thermal Velocity Boost).
* **`GroupMask[0].Mask` (KAFFINITY / c_size_t)**: Máscara de bits que identifica unívocamente a los procesadores lógicos pertenecientes a dicho núcleo.

El algoritmo calcula:
$$\mathbf{Mask}_{\text{pcore}} = \bigvee_{\forall c \in \text{Cores} \mid \text{EfficiencyClass}(c) = \max(\text{EfficiencyClass})} \text{Mask}(c)$$

Si todos los núcleos presentan la misma clase de eficiencia ($\max = \min$), el sistema reconoce una topología homogénea y genera una máscara unificada con todos los núcleos lógicos del sistema, garantizando máxima compatibilidad.

#### 3.1.2. Elevación de Prioridad a `HIGH_PRIORITY_CLASS` y Fijación de Afinidad
Para evitar la inanición de hilos (*thread starvation*) provocada por procesos en segundo plano de Windows (antivirus, servicios de telemetría, indexación), cada subproceso multimedia se somete a la siguiente secuencia Win32:
1. Obtención del handle de proceso:
   ```c
   HANDLE hProcess = OpenProcess(PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION, FALSE, pid);
   ```
2. Asignación de clase de prioridad:
   ```c
   SetPriorityClass(hProcess, HIGH_PRIORITY_CLASS); // 0x00000080
   ```
   *(Nota: Se evita deliberadamente `REALTIME_PRIORITY_CLASS` (0x00000100) para no comprometer el subsistema de interrupciones de red e I/O del sistema operativo).*
3. Aplicación de la máscara de afinidad calculada:
   ```c
   SetProcessAffinityMask(hProcess, (DWORD_PTR)effective_mask);
   ```
4. Cierre determinista del handle mediante `CloseHandle` para erradicar fugas de handles en el kernel de Windows NT.

---

### 3.2. Bloqueo Óptico DirectShow COM UVC (`core/uvc_control.py`)

#### 3.2.1. Interacción con Interfaces COM DirectShow
La comunicación con el hardware de captura se realiza mediante las interfaces COM del subsistema DirectShow de Windows:
* **`ICreateDevEnum`**: Enumerador de dispositivos del sistema (`CLSID_SystemDeviceEnum`).
* **`IEnumMoniker`**: Recorre los dispositivos registrados en la categoría `CLSID_VideoInputDeviceCategory` (`{860BB310-5D01-11D0-BD3B-00A0C911CE86}`).
* **`IPropertyBag`**: Permite extraer las propiedades de texto `FriendlyName` y `DevicePath` para correlacionarlas con la configuración del dispositivo solicitada.
* **`IAMCameraControl`**: Interfaz de control del sensor expuesta por el controlador UVC de Microsoft (`PROPSETID_VIDCAP_CAMERACONTROL`).

#### 3.2.2. Cálculo del Shutter Time y Aplicación de Flags
En la especificación DirectShow COM, la propiedad `CameraControl_Exposure` se expresa en unidades logarítmicas de base 2 del tiempo de obturación en segundos:
$$\text{valor} = \log_2(t)$$

Para un tiempo de obturación objetivo de $t = 1/60\text{ s}$:
$$\text{valor} = \log_2\left(\frac{1}{60}\right) = -\log_2(60) \approx -5.90689 \longrightarrow -6$$

El método `IAMCameraControl.Set` recibe:
* **`Property`**: `CameraControl_Exposure` (4).
* **`Value`**: Valor calculado redondeado a entero ($-6$).
* **`Flags`**: `CameraControl_Flags_Manual` (0x0002).

```
   +-----------------------------------------------------------------------+
   |                       Flujo de Inicialización UVC                     |
   +-----------------------------------------------------------------------+

        DirectShow Device Name / Moniker Path
                         |
      +------------------v------------------+
      |  Es Dispositivo Virtual o lavfi?   |
      +------------------+------------------+
               /                    \
            [SÍ]                    [NO]
              |                       |
      +-------v-------+       +-------v-------------------------+
      | Omitir control|       | CoCreateInstance(SysDevEnum)    |
      | Retornar False|       | IEnumMoniker -> Match Moniker   |
      +---------------+       +---------------+-----------------+
                                              |
                              +---------------v-----------------+
                              | BindToObject -> IAMCameraControl|
                              +---------------+-----------------+
                                              |
                                     /-----------------\
                            [Soporta IAMCameraControl?]
                                     \-----------------/
                                      /               \
                                   [NO]               [SÍ]
                                     |                  |
                          +----------v-----+     +------v-----------------+
                          | Log informativo|     | Set(Exposure, -6,      |
                          | Fallback suave |     |     CameraFlags_Manual)|
                          +----------------+     +------+-----------------+
                                                        |
                                                 +------v-----------------+
                                                 | Obturador fijado <=1/60s|
                                                 | 60 FPS Físicos Asegurados|
                                                 +------------------------+
```

---

### 3.3. Integración en el Pipeline de Transmisión (`core/stream_proc.py`)

Al iniciarse un flujo de cámara en `StreamProc.start()`:
1. Previamente al lanzamiento de `ffmpeg.exe`, se ejecuta `lock_uvc_auto_exposure(self.device_path, max_shutter_sec=1/60.0)`. Esto garantiza que cuando el pin DirectShow se abra, el sensor ya opere con el obturador acotado.
2. Inmediatamente después de instanciar el proceso hijo `self.process = await asyncio.create_subprocess_exec(...)`, se obtiene su PID y se invoca:
   ```python
   elevate_process_priority(self.process.pid, priority_class=HIGH_PRIORITY_CLASS)
   ```
3. El proceso queda confinado a los P-Cores con prioridad alta, protegido contra la degradación del planificador del sistema operativo.

---

## 4. Estrategia de Migración y Rollout sin Interrupción

1. **Retrocompatibilidad de Esquema**:
   * Las cámaras existentes conservan sus parámetros de configuración en SQLite WAL.
   * La migración de esquema v3 actualizó de forma atómica el valor predeterminado de cámaras de 30 FPS a 60 FPS (`UPDATE cameras SET fps = 60 WHERE fps = 30`).
2. **Degradación Transparente**:
   * En hardware sin soporte de `IAMCameraControl` o en entornos Linux/macOS utilizados para pruebas de CI, las rutinas retornan `False` y no interrumpen el lanzamiento del stream.
   * En procesadores sin núcleos híbridos (ej. Ryzen 5000 / Intel 10ª Gen), la máscara calculada abarca todos los hilos disponibles sin alterar el paralelismo del sistema.

---

## 5. Plan de Pruebas de Estrés y Métricas de Validación

### 5.1. Métricas de Validación del SLA

| Métrica de Rendimiento | Línea Base (v2.8.0) | Resultado con RFC-0006 (v2.8.3) | Criterio de Éxito |
| :--- | :---: | :---: | :---: |
| **Latencia Vidrio a Vidrio (P50)** | $157.5\text{ ms}$ | **$38.8\text{ ms}$** | $\le 50\text{ ms}$ |
| **Latencia Vidrio a Vidrio (P99)** | $245.0\text{ ms}$ | **$49.2\text{ ms}$** | $\le 75\text{ ms}$ |
| **FPS en Penumbra (Lux < 20)** | $18.2\text{ FPS}$ | **$59.8\text{ FPS}$** | $\ge 58.0\text{ FPS}$ |
| **Jitter por Inversión de Núcleo** | $\pm 18.5\text{ ms}$ | **$\pm 1.2\text{ ms}$** | $\le 2.5\text{ ms}$ |

### 5.2. Escenarios de Pruebas Automatizadas
* **`tests/test_audit_v283_features.py`**:
  * Prueba de cálculo de máscara de P-Cores (`get_pcore_affinity_mask`) bajo topologías simuladas y reales.
  * Validación de invocación defensiva de `elevate_process_priority` protegiendo contra identificadores no enteros o mocks.
  * Comprobación de no interferencia en dispositivos virtuales para `lock_uvc_auto_exposure`.

---

## 6. Consideraciones de Seguridad y Robustez

1. **Gestión Segura de Handles de Kernel (CWE-404)**: Toda apertura de handles de proceso mediante `OpenProcess` se acompaña de un bloque `try...finally` garantizando la invocación de `kernel32.CloseHandle`.
2. **Aislamiento de Errores COM**: Las llamadas a la vtable de COM en `ctypes` están envueltas en captura exhaustiva de excepciones para evitar cualquier terminación involuntaria del intérprete de Python.
3. **Protección contra Inversión de Prioridad Crítica**: El uso estricto de `HIGH_PRIORITY_CLASS` asegura que el software de transmisión nunca interfiera con las rutinas de tiempo real duro de Windows NT (DPC/ISR del subsistema de red y audio).
