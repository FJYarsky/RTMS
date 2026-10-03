# ADR-0021: Control DirectShow COM UVC y Bloqueo de Auto-Exposición para Prevención de Caídas de FPS

* **Estado**: Aceptado
* **Fecha**: 2026-10-03
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Hardware / Video / DirectShow
* **Subflujos y Componentes**: [`core/uvc_control.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/uvc_control.py), [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py)
* **Vínculos**: Extiende [ADR-0002](0002-negociacion-dinamica-formatos-directshow.md) y se formaliza en [RFC-0006](../rfc/RFC-0006-aislamiento-subprocesos-p-cores-y-control-optico-uvc.md)

---

## 1. Contexto

Las cámaras web USB basadas en el estándar USB Video Class (UVC) (tales como dispositivos de la serie Logitech C920/C922/BRIO y sensores genéricos USB 2.0 y 3.0) vienen configuradas de fábrica con algoritmos de control de exposición automática (*Auto-Exposure*) gestionados internamente por el microcontrolador del sensor.

En condiciones de iluminación ambiental subóptima o en entornos de baja luminosidad (típicos en cabinas de streaming o sets de producción sin iluminación cinematográfica dedicada), el firmware de la cámara web intenta compensar la falta de lux aumentando el tiempo de integración del obturador del sensor físico más allá de la ventana admisible de $16.66\text{ ms}$ requerida para sostener 60 FPS (o $33.33\text{ ms}$ para 30 FPS). En casos severos, el sensor extiende el obturador a $40\text{ ms}$, $50\text{ ms}$ o $66.6\text{ ms}$.

La consecuencia técnica inmediata es crítica:
1. **Colapso físico del framerate**: La cámara web reduce unilateralmente la tasa de fotogramas físicos entregados a DirectShow a 15-20 FPS.
2. **Invisibilidad para la cadena de software**: FFmpeg y el demuxer DirectShow reciben menos fotogramas en el bus USB. Ningún parámetro de línea de comandos en FFmpeg (`-framerate 60`, `-r 60`) puede subsanar esta deficiencia porque los fotogramas físicamente nunca son emitidos por el silicio de la cámara.
3. **Tartamudeo y pérdida de fluidez visual**: En la transmisión hacia OBS/vMix, la fluidez a 60 FPS desaparece, provocando duplicación de fotogramas y degradación de la experiencia del espectador.

---

## 2. Factores Decisivos

* **Garantía inquebrantable de 60 FPS**: La promesa de valor de RTMS es el streaming multicámara fluido a 60 FPS estables.
* **Transparencia operativa**: El bloqueo de la exposición debe ejecutarse automáticamente sin necesidad de software propietario del fabricante (ej. Logitech G HUB, Razer Synapse) ni ventanas modales que bloqueen la automatización sin cabeza (*headless*).
* **Degradación controlada**: Si una fuente de video es virtual (ej. generadores sintéticos `testsrc2`, OBS Virtual Camera) o una cámara no implementa la interfaz COM requerida, el sistema debe degradar silenciosamente sin abortar el flujo.
* **Preservación de la inicialización COM**: Debe interactuar limpiamente con el modelo de subprocesos COM STA/MTA de Windows sin corromper el hilo de ejecución de Python.

---

## 3. Alternativas Evaluadas

### Opción A: Desplegar el diálogo nativo de propiedades de DirectShow (`-show_video_device_dialog true`) (Descartada)
* *Ventajas*: Permite al usuario manipular el control manual del controlador DirectShow.
* *Desventajas*: Despliega una ventana modal interactiva de Windows que bloquea por completo la inicialización automatizada en background, incompatibilizando la suite con automatizaciones y clientes headless.

### Opción B: Duplicación sintética de cuadros en FFmpeg (`-vf fps=fps=60`) (Descartada)
* *Ventajas*: FFmpeg emite 60 paquetes por segundo al receptor.
* *Desventajas*: No resuelve el problema real; multiplica fotogramas repetidos de un sensor que entrega 15 FPS, manteniendo el aspecto visual espasmódico y consumiendo ancho de banda innecesario.

### Opción C: Dependencia en utilidades externas del fabricante (Descartada)
* *Ventajas*: La configuración se realiza en el driver.
* *Desventajas*: Inviable en producción heterogénea; introduce bloatware y no es programático ni reproducible.

### Opción D (Elegida): Intervención de bajo nivel mediante interfaz DirectShow COM `IAMCameraControl`
* *Ventajas*: Control directo sobre la propiedad `CameraControl_Exposure` en modo manual (`CameraControl_Flags_Manual`) forzando el tiempo de obturación a $\le 1/60\text{ s}$. Opera en microsegundos antes de que FFmpeg abra el pin de captura, garantizando que el hardware inicie directamente en el modo óptico correcto.
* *Desventajas*: Requiere instanciación manual del enumerador de dispositivos DirectShow (`ICreateDevEnum`) e interfaces COM mediante punteros vtable en `ctypes`.

---

## 4. Decisión

Se decide implementar el subsistema [`core/uvc_control.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/uvc_control.py) y su función central `lock_uvc_auto_exposure(device_path, max_shutter_sec=1/60.0)`.

### Arquitectura de Control Óptico DirectShow COM

1. **Instanciación del Enumerador de Dispositivos**:
   * Inicializa la infraestructura COM mediante `ole32.CoInitialize(None)`.
   * Crea una instancia de `CLSID_SystemDeviceEnum` con interfaz `ICreateDevEnum` (`IID_ICreateDevEnum`).
   * Genera el enumerador de la categoría de captura de video `CLSID_VideoInputDeviceCategory` (`{860BB310-5D01-11D0-BD3B-00A0C911CE86}`).

2. **Resolución de Moniker y Bind de Almacenamiento**:
   * Itera los dispositivos DirectShow mediante `IEnumMoniker.Next`.
   * Enlaza el almacenamiento a `IPropertyBag` para extraer `FriendlyName` y `DevicePath`.
   * Realiza un emparejamiento estricto contra el identificador provisto en la configuración de la cámara.

3. **Invocación de `IAMCameraControl`**:
   * Enlaza el filtro base del dispositivo (`IBaseFilter`) y solicita la interfaz `IAMCameraControl` (`PROPSETID_VIDCAP_CAMERACONTROL`).
   * La interfaz DirectShow define la escala de exposición como el logaritmo en base 2 del tiempo de obturación en segundos ($val = \log_2(t)$). Para $t = 1/60\text{ s}$, el valor matemático es $\approx -5.906$, lo cual redondea a $-6$.
   * Consulta el rango admisible mediante `IAMCameraControl.GetRange(CameraControl_Exposure)`.
   * Aplica `IAMCameraControl.Set(CameraControl_Exposure, target_val, CameraControl_Flags_Manual)`.
   * Si la cámara rechaza la asignación manual o no implementa la interfaz, la función captura la excepción de forma segura y devuelve `False` sin interrumpir la operación.

```
  +--------------------------------------------------------------+
  |              StreamProc / Inicialización de Cámara           |
  +--------------------------------------------------------------+
                                 |
              lock_uvc_auto_exposure(device_path, 1/60.0)
                                 |
  +------------------------------v-------------------------------+
  |        DirectShow COM Subsystem (core/uvc_control.py)        |
  +--------------------------------------------------------------+
                                 |
     1. CoCreateInstance(CLSID_SystemDeviceEnum)
     2. Enumerate VideoInputCategory -> Match Moniker
     3. QueryInterface(IID_IAMCameraControl)
     4. Set(CameraControl_Exposure, -6, CameraControl_Flags_Manual)
                                 |
  +------------------------------v-------------------------------+
  |             Hardware UVC Firmware / Sensor Óptico            |
  |     - Auto-Exposure deshabilitada                            |
  |     - Shutter fijado a <= 1/60s (<= 16.6ms)                  |
  |     - 60 FPS físicos estables e ininterrumpidos              |
  +--------------------------------------------------------------+
```

---

## 5. Consecuencias

### Positivas
* **Estabilidad Absoluta a 60 FPS**: Se erradica por completo la caída invisible de framerate a 15-20 FPS provocada por el sensor en condiciones de baja iluminación.
* **Integración Zero-Bloat**: No requiere software de terceros ni controladores propietarios; utiliza la capa estándar del sistema operativo Windows.
* **Transparencia y Seguridad**: Las fuentes virtuales y cámaras que no soportan la interfaz degradan elegantemente sin provocar excepciones ni bloqueos.

### Negativas
* **Sub-exposición visual en penumbra extrema**: Al impedir que el sensor alargue la exposición, la imagen capturada en penumbra severa puede exhibir menor brillo. Este efecto es físicamente deseable en producción profesional, compensándose mediante la ganancia del sensor (ISO/Gain) o la iluminación del estudio sin comprometer la cadencia de cuadros.
