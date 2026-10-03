# ADR-0022: Ciclo de Vida Lazy y Apagado Suave con Período de Gracia para MediaMTX

* **Estado**: Aceptado
* **Fecha**: 2026-10-03
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Core / Recursos / Ciclo de Vida
* **Subflujos y Componentes**: ``core/mediamtx_mgr.py``, ``main.py``, ``core/stream_manager.py``
* **Vínculos**: Modifica y clarifica [ADR-0001](ADR-0001-Adopcion-Mediamtx-Broker-Central) y complementa [ADR-0009](ADR-0009-Blindaje-Kernel-Win32-Job-Objects)

---

## 1. Contexto

En el diseño original de RTMS documentado en [ADR-0001](ADR-0001-Adopcion-Mediamtx-Broker-Central), el servidor de medios MediaMTX (`mediamtx.exe`) se inicializaba de manera incondicional durante el arranque del sistema (`main.py`), actuando como un demonio residente en segundo plano durante toda la sesión de la aplicación.

Si bien esta estrategia garantizaba disponibilidad instantánea del broker para protocolos SRT y WebRTC WHEP, introducía desventajas operativas notables en escenarios de uso común:
1. **Consumo ocioso innecesario de recursos**: MediaMTX retiene aproximadamente $50\text{ MB}$ de memoria RAM y múltiples hilos en segundo plano incluso cuando el operador transmite exclusivamente mediante **UDP Unicast o Multicast directo**, los cuales no requieren ningún servidor intermediario (*zero-broker architecture*).
2. **Retención permanente de sockets de red**: MediaMTX enlaza de manera estática los puertos `8888` (HLS), `8889` (WebRTC), `8890` (SRT) y `9997` (API de control), lo que puede generar conflictos con otro software de producción broadcast que comparta la misma estación de trabajo.
3. **Falta de elasticidad**: El ciclo de vida del broker estaba rígidamente acoplado al inicio y parada de la aplicación global, sin correlación con la demanda real de los flujos de video.

---

## 2. Factores Decisivos

* **Eficiencia de huella de memoria**: Reducir el consumo base del sistema al mínimo posible en reposo y en modos de transmisión punto a punto.
* **Transparencia bajo demanda (*Just-in-Time Provisioning*)**: Cuando un flujo SRT se inicie o un cliente solicite una vista previa WebRTC WHEP, MediaMTX debe levantarse de forma transparente y determinista en menos de 500 ms.
* **Resiliencia ante reconexiones rápidas (Evitar el efecto *Thrashing*)**: Si un operador reinicia una cámara o cambia de perfil, el broker no debe apagarse y encenderse de manera oscilatoria en fracciones de segundo.
* **Compatibilidad hacia atrás**: Todo el código cliente y las rutas API existentes deben continuar interactuando con MediaMTX a través del singleton `mediamtx_manager` sin percatarse de su estado latente.

---

## 3. Alternativas Evaluadas

### Opción A: Mantener el demonio persistente incondicional (Descartada)
* *Ventajas*: Cero latencia de inicialización en el primer flujo SRT.
* *Desventajas*: Desperdicio continuo de $50\text{ MB}$ de memoria RAM y ocupación innecesaria de 4 puertos de red en estaciones de trabajo que sólo usan streaming UDP.

### Opción B: Apagado síncrono inmediato al desconectar la última cámara (Descartada)
* *Ventajas*: Liberación instantánea de memoria.
* *Desventajas*: Provoca inestabilidad severa (*process thrashing*). Durante reinicios controlados de cámaras, renegociación de parámetros o reconexiones de red, MediaMTX se destruiría y crearía repetidamente, interrumpiendo negociaciones ICE de WebRTC y saturando el planificador del sistema operativo.

### Opción C (Elegida): Ciclo de vida Lazy bajo demanda con conteo de referencias y supervisor de inactividad con período de gracia de 20 segundos
* *Ventajas*: Inicio diferido automático sólo cuando es requerido; conteo de referencias para flujos SRT activos y registro de actividad WebRTC; temporizador de gracia de 20 segundos antes de la terminación controlada; liberación garantizada de sockets y RAM cuando no hay tráfico.
* *Desventajas*: El primer arranque bajo demanda incurre en una latencia de $\approx 350\text{ ms}$, la cual es absorbida de forma totalmente asíncrona antes de despachar el comando de FFmpeg.

---

## 4. Decisión

Se decide desacoplar MediaMTX del arranque incondicional de la aplicación e implementar una gobernanza de ciclo de vida elástica y perezosa (*lazy lifecycle*) en ``core/mediamtx_mgr.py``:

1. **Supresión del Arranque en `main.py`**:
   * En el punto de entrada de la aplicación, se retira la invocación directa e incondicional a `mediamtx_manager.start()`. La aplicación inicia en modo ligero consumiendo únicamente $\sim 12\text{ MB}$ de RAM.

2. **Aprovisionamiento Bajo Demanda (`ensure_started`)**:
   * Cuando `StreamManager.start_stream()` detecta un flujo con protocolo `srt`, invoca `await mediamtx_manager.ensure_started(srt_port)`.
   * Cuando la API REST procesa una solicitud de señalización WebRTC en `/api/stream/{device_path}/whep`, invoca `await mediamtx_manager.ensure_started()`.
   * Si el proceso `_process` ya está activo y respondiendo a su API local, el método retorna `True` inmediatamente. Si está inactivo, ejecuta el arranque asíncrono, configura los puertos en `config/mediamtx.yml` y lanza el supervisor watchdog.

3. **Conteo de Referencias de Flujos SRT y Registro WebRTC**:
   * Mantiene un conjunto interno `_active_srt_streams: set`.
   * Al iniciar un flujo SRT se ejecuta `register_srt_stream(device_path)`; al detenerse, `unregister_srt_stream(device_path)`.
   * Cada solicitud WHEP ejecuta `register_webrtc_activity()`, actualizando la marca de tiempo `_last_activity_time`.

4. **Bucle Supervisor de Inactividad con Período de Gracia (`_inactivity_watchdog_loop`)**:
   * Un bucle asíncrono verifica cada 2.0 segundos el estado del servidor.
   * Si no existen flujos SRT registrados localmente ni configurados con auto-inicio, y la diferencia `loop_time - self._last_activity_time >= 20.0` segundos, MediaMTX se apaga limpiamente mediante `self.stop()`.
   * El período de gracia de 20 segundos actúa como una banda de histéresis temporal que tolera reintentos de conexión, reinicios de perfiles o cambio rápido de vistas previas.

```
                  +-----------------------------------+
                  |   Arranque RTMS (Modo Reposo)     |
                  |     MediaMTX: INACTIVO (0 MB)     |
                  +-----------------------------------+
                                    |
                Flujo SRT iniciado / Visor WHEP abierto
                                    |
                  +-----------------v-----------------+
                  |     ensure_started() [Lazy Init]  |
                  |     MediaMTX: ACTIVO (~50 MB)     |
                  +-----------------------------------+
                                    |
                 Último flujo cerrado / Visor desconectado
                                    |
                  +-----------------v-----------------+
                  |   Período de Gracia (Hysteresis)  |
                  |         Cuenta regresiva: 20s     |
                  +-----------------------------------+
                        /                       \
        [Actividad dentro de 20s]     [Sin actividad > 20s]
                   |                             |
       +-----------v-----------+     +-----------v-----------+
       | Cancela temporizador  |     | stop() Apagado Suave  |
       | Continúa activo       |     | Libera RAM y Sockets  |
       +-----------------------+     +-----------------------+
```

---

## 5. Consecuencias

### Positivas
* **Optimización Drástica de Recursos**: La huella de memoria base del sistema se reduce en más de un 75% cuando sólo se opera con cámaras directas por UDP.
* **Liberación Limpia de Puertos**: Los puertos `8888`, `8889`, `8890` y `9997` permanecen cerrados y disponibles para otros servicios del host salvo cuando realmente se están utilizando.
* **Estabilidad Operativa sin Thrashing**: La histéresis de 20 segundos previene interrupciones accidentales durante cambios de configuración o reconexiones de red en vivo.

### Negativas
* **Pequeña latencia en el primer arranque SRT**: La primera cámara que requiera MediaMTX experimentará una espera asíncrona de $\approx 350\text{ ms}$ mientras el ejecutable arranca y enlaza sus sockets, completamente transparente para el usuario final.
