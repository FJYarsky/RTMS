# ADR-0017: Taxonomía Formal de Errores, Máquina de Estados Finita y Watchdog con Backoff Exponencial

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Core / Resiliencia / Tolerancia a Fallos / Concurrencia
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
Los procesos de captura de video sobre hardware físico están expuestos a una multiplicidad de fallos asimétricos:
- Desconexión física accidental de cables USB (*device unplug*).
- Fallos de codificación por agotamiento de sesiones NVENC en GPUs de consumo (*encoder error*).
- Conflictos de sockets por procesos externos (*port collision*).
- Parámetros inválidos en la negociación DirectShow (*configuration error*).
- Corrupción de tramas o caídas del enlace de red local (*network error*).

En arquitecturas ingenuas de streaming, ante cualquier salida de FFmpeg con código distinto de cero (`returncode != 0`), el supervisor reintenta el arranque de inmediato en un bucle cerrado (*tight loop*). Esto genera:
1. Saturación del 100% de la CPU por miles de intentos de spawn por minuto.
2. Imposibilidad de discernir si el problema requiere acción del usuario (cámara desconectada) o es una falla transitoria de red recuperable automáticamente.
3. Ausencia de un estado del sistema predecible y trazable para los operadores de OBS o la mesa técnica.

## 2. Factores Decisivos (Decision Drivers)
* **Modelado Riguroso del Ciclo de Vida**: Cada flujo de video debe gobernarse mediante una Máquina de Estados Finita (FSM) determinista, con transiciones válidas y prohibición de estados ilegales.
* **Taxonomía Semántica de Errores**: Clasificar inequívocamente la causa raíz de cada fallo para determinar la política de recuperación adecuada.
* **Protección contra Bucles de Reintento Frecuente**: Aplicar algoritmos de retroceso exponencial (*exponential backoff*) y límite de reintentos máximos antes de requerir intervención manual.
* **Telemetría no Bloqueante de Progreso**: Parsear el estado de FFmpeg evitando bloqueos de buffer del sistema operativo (Windows pipe deadlock).

## 3. Opciones Consideradas
* **Opción A (Reinicio Incondicional en Bucle `while True`)**: Reiniciar el proceso siempre que muera con una pausa estática de 1 segundo.
  - *Desventajas*: Catastrófico si el hardware fue desconectado; consume ciclos de CPU inútiles e inunda los archivos de log con millones de líneas.
* **Opción B (Detención Inmediata ante Cualquier Error sin Autorrecuperación)**: Marcar el stream como fallido al primer error.
  - *Desventajas*: Fragilidad inadmisible; un micro-corte de red transitorio de 50 ms abortaría permanentemente la emisión en vivo.
* **Opción C (FSM con Taxonomía de 8 Categorías de Error y Watchdog con Ventana de Estabilidad)**:
  - FSM con estados explícitos (`STOPPED`, `STARTING`, `RUNNING`, `ERROR`, `RESTARTING`, `RECOVERING`, `STOPPING`, `DISCONNECTED`, `MANUAL_INTERVENTION_REQUIRED`).
  - Clasificación en `ErrorCategory` (`CONFIGURATION`, `DEVICE`, `ENCODER`, `NETWORK`, `PORT_COLLISION`, `PROCESS`, `AUTHENTICATION`, `UNKNOWN`).
  - Supervisor watchdog con intervalo de 2 segundos, backoff exponencial, límite de 5 fallos consecutivos y restablecimiento de contador tras 60 segundos de emisión estable.

## 4. Decisión
Se adopta la **Opción C**:
1. En [`core/stream_proc.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_proc.py), se define formalmente la enumeración de estados:
   ```python
   class State(str, Enum):
       STOPPED = "stopped"
       STARTING = "starting"
       RUNNING = "running"
       ERROR = "error"
       RESTARTING = "restarting"
       RECOVERING = "recovering"
       STOPPING = "stopping"
       DISCONNECTED = "disconnected"
       MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"
   ```
2. Se implementa la taxonomía [`ErrorCategory`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_proc.py) para análisis de trazas de FFmpeg:
   - `DEVICE`: Dispositivo DirectShow no encontrado o desenchufado. Transiciona a `DISCONNECTED`.
   - `ENCODER`: Fallo de NVENC/QSV. Dispara la política de degradación resiliente a CPU (`force_cpu=True`).
   - `PORT_COLLISION`: Puerto ocupado. Invoca `port_manager.reallocate_if_collided()`.
   - `NETWORK`: Pérdida de socket SRT. Activa backoff exponencial.
3. **Mecanismo de Lectura de Progreso sin Deadlocks**:
   - En lugar de capturar stderr mediante regex costosas, se inyecta `-progress pipe:1` en los argumentos de FFmpeg y se lee `stdout` línea por línea procesando bloques clave-valor (`fps=...`, `bitrate=...`, `drop_frames=...`).
   - Esto evita el infame deadlock de pipes de Windows donde el subproceso se bloquea si el buffer de stderr del sistema operativo (4 KB) se llena y el padre no lo lee a tiempo.
4. **Política del Watchdog y Recuperación**:
   - En [`core/stream_manager.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_manager.py), el watchdog evalúa cada 2 segundos los procesos activos.
   - Si un stream falla, incrementa `error_count` ($k$) y calcula el tiempo de espera con backoff exponencial:
     $$T_{\mathrm{wait}} = \min(2^k, 30) \quad (\text{segundos})$$
   - Si un stream permanece en estado `RUNNING` durante más de 60 segundos continuos (`STABILITY_THRESHOLD_SECONDS`), se reinicia `error_count = 0` reconociendo la estabilidad de la transmisión.
   - Si `error_count >= 5`, se cancelan los reintentos automáticos y se transiciona a `MANUAL_INTERVENTION_REQUIRED`, protegiendo la CPU y notificando al operador en el HUD.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Máxima Tolerancia a Fallos**: Cortes esporádicos de red se recuperan solos en segundos sin que el operador deba intervenir.
* **Protección del Host ante Desconexión de Hardware**: Si una cámara se desenchufa, el sistema detiene los intentos agresivos de reinicio y queda a la espera de que el hotplug detecte la reconexión.
* **Trazabilidad Forense Completa**: La categorización semántica del error permite diagnósticos inmediatos en la interfaz web y en los logs JSON ECS.
* **Cero Bloqueos por Deadlocks de Pipes**: El consumo continuo de `pipe:1` garantiza que FFmpeg nunca se congele por buffers de salida saturados en el kernel.

### Consecuencias Negativas / Limitaciones (-)
* En fallos no catalogados (`UNKNOWN`), el sistema debe realizar una inspección heurística de las últimas 20 líneas de logs en memoria para estimar la mejor ruta de recuperación.

## 6. Validación y Cumplimiento
* Pruebas de resiliencia, desconexión de hardware y reintentos en [`tests/test_stream_resilience.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_stream_resilience.py) y [`tests/test_stream_lifecycle.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_stream_lifecycle.py).
* Verificación de la taxonomía de errores en [`tests/test_audit_v260_features.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_v260_features.py).
