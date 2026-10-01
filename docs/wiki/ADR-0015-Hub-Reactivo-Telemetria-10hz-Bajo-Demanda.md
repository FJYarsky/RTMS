# ADR-0015: Hub Reactivo de Telemetría a 10 Hz con Suscripción Bajo Demanda y Doble Cadencia

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Telemetría / WebSockets / Concurrencia / Rendimiento / GUI
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
Para proporcionar una experiencia de monitoreo en tiempo real comparable a consolas de producción profesional, la interfaz de usuario de RTMS (Dashboard HUD) requiere métricas continuas y fluidas:
- FPS instantáneos por cámara (fluctuación de 30 o 60 FPS).
- Bitrate de salida codificado en kilobits por segundo.
- Velocidad de procesamiento de FFmpeg (factor de tiempo real, ej. `1.0x`).
- Cuadros omitidos (*dropped frames*) acumulados.
- Consumo global de CPU del host, memoria RAM, GPU (vRAM y carga del motor 3D/video) y rendimiento de red (KB/s transmitidos/recibidos).

El enfoque tradicional de consultar la API mediante peticiones HTTP repetitivas (*polling* HTTP cada 500 ms) generaba:
1. Elevado consumo de CPU por apertura/cierre continuo de sockets TCP y parseo masivo de cabeceras HTTP.
2. Latencia y desincronización visual evidente en los indicadores de la interfaz gráfica.
3. Consumo innecesario de energía y CPU en segundo plano incluso cuando el usuario minimizaba la aplicación o cerraba el navegador web.
4. Sobrecarga excesiva si se llamaba a librerías pesadas de métricas de sistema (como `psutil.cpu_percent` o llamadas WMI de Windows) a frecuencias superiores a 5 Hz.

## 2. Factores Decisivos (Decision Drivers)
* **Alta Fluidez Visual (10 Hz / 100 ms)**: La telemetría en vivo de las cámaras y gráficos debe actualizarse 10 veces por segundo para percibir caídas de cuadros y fluctuaciones de bitrate instantáneas.
* **Cero Consumo en Modo Inactivo (On-Demand Activation)**: Cuando no hay ningún navegador ni ventana gráfica conectada, el bucle de telemetría debe suspenderse por completo (0% de CPU consumido).
* **Mitigación de Sobrecarga del Sistema Operativo (Doble Cadencia)**: Métricas pesadas que bloquean llamadas del kernel (`psutil.cpu_percent`) no deben ejecutarse a 10 Hz, sino a una frecuencia amortiguada de 1 Hz.
* **Transmisión de Eventos Reactivos Inmediatos**: Cambios de estado discretos (inicio, detención, desconexión de hardware, advertencias críticas) deben empujarse instantáneamente sin esperar el siguiente ciclo de reloj.
* **Seguridad de Hilo (Thread-Safety)**: Capacidad de emitir eventos desde hilos secundarios de Windows (como el System Tray) hacia el bucle asíncrono de FastAPI sin deadlocks.

## 3. Opciones Consideradas
* **Opción A (HTTP Polling Corto desde el Frontend)**: El cliente realiza `fetch('/api/system/telemetry')` cada 200 ms.
  - *Desventajas*: Sobrecarga masiva de la pila HTTP; sobrecarga de miles de peticiones por minuto en Uvicorn; no permite empujar eventos reactivos instantáneos del backend.
* **Opción B (Server-Sent Events - SSE unidireccional)**: Flujo de eventos continuo HTTP unidireccional.
  - *Desventajas*: No permite comunicación bidireccional si se requiere control en el mismo canal; soporte inconsistente en proxies y manejo engorroso de reconexiones en WebView2.
* **Opción C (Hub WebSocket Reactivo a 10 Hz con Activación Dinámica y Muestreo Asimétrico)**:
  - Establecer una conexión full-duplex vía WebSocket en `/api/ws/telemetry`.
  - Iniciar la tarea de muestreo `_ticker_loop()` a 10 Hz (100 ms) **únicamente cuando el número de clientes conectados sea $\ge 1$**.
  - Cancelar automáticamente el ticker cuando el último cliente se desconecte.
  - Muestreo desacoplado de doble cadencia: métricas pesadas de CPU/RAM a 1 Hz (cada 10 ticks), y métricas ligeras (GPU, red, FPS/bitrate de streams en memoria) a 10 Hz.

## 4. Decisión
Se adopta la **Opción C**:
1. Se crea la clase ``TelemetryWebSocketHub`` en `core/telemetry_hub.py`.
2. Al conectarse un cliente en ``api/routes/ws.py``, se registra en el hub mediante `await telemetry_hub.register(websocket)`:
   - Si `client_count == 1`, se instancia atómicamente la tarea `_ticker_task = asyncio.create_task(self._ticker_loop())`.
3. Al desconectarse un cliente (`unregister`):
   - Si `client_count == 0`, se cancela `_ticker_task`, deteniendo el bucle de muestreo por completo.
4. **Algoritmo de Muestreo de Doble Cadencia**:
   - Cada ciclo de 100 ms (`start_time = time.monotonic()`):
     - Si `_tick_counter % 10 == 1` (cadencia 1 Hz), se actualizan métricas del SO: `psutil.cpu_percent(interval=None)` y memoria virtual.
     - En cada tick (cadencia 10 Hz), se consultan métricas ligeras desde contadores en RAM: `gpu_reader.get_metrics()`, `net_tracker.get_metrics()` y los atributos `current_fps`, `current_bitrate_kbps`, `current_dropped_frames` del diccionario de procesos `StreamProc`.
5. Se implementa `notify_event_threadsafe(event_type, data, loop)` que utiliza `asyncio.run_coroutine_threadsafe` para inyectar eventos reactivos desde hilos de hardware o menú de bandeja sin bloquear la llamada.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Monitoreo Ultrasensible a 10 Hz**: El usuario observa la respuesta del sistema en tiempo real con latencias de visualización inferiores a 100 ms.
* **Cero Desperdicio de CPU**: Con la ventana cerrada o minimizada, el hub apaga el bucle de telemetría, reduciendo la huella de CPU de RTMS en segundo plano a prácticamente 0.0%.
* **Amortiguación de Sobrecarga en el Host**: El muestreo de `psutil` a 1 Hz evita saturar las llamadas al kernel del sistema operativo con consultas repetitivas de contadores de rendimiento.
* **Resiliencia ante Desconexiones**: Los clientes que cierran pestañas de manera abrupta son detectados y eliminados del conjunto sin provocar excepciones en el servidor.

### Consecuencias Negativas / Limitaciones (-)
* En redes con inspección profunda de paquetes (firewalls DPI agresivos) que bloquean WebSockets, la conexión debe contar con un fallback de reintento automático en el cliente JavaScript (`gui/static/app.js`).

## 6. Validación y Cumplimiento
* Pruebas del ciclo de vida del WebSocket y del ticker en ``tests/test_telemetry.py``.
* Verificación de resistencia ante desconexiones intempestivas en ``tests/test_fuzzing_and_boundaries.py``.
