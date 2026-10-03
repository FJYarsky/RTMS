# ADR-0023: Canonicidad de UDP Unicast y Desmitificación de SRT como Protocolo Predeterminado

* **Estado**: Aceptado
* **Fecha**: 2026-10-03
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: Red / Protocolos / Streaming
* **Subflujos y Componentes**: [`core/command_builder.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/command_builder.py), [`core/stream_proc.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_proc.py), [`api/routes/streams.py`](file:///C:/Users/joaqu/Desktop/RTMS/api/routes/streams.py), [`gui/static/app.js`](file:///C:/Users/joaqu/Desktop/RTMS/gui/static/app.js)
* **Vínculos**: Modifica y sucede parcialmente a [ADR-0001](0001-adopcion-mediamtx-broker-central.md) y [ADR-0005](0005-distribucion-udp-multicast-unicast.md)

---

## 1. Contexto

En las fases tempranas del desarrollo de RTMS, el protocolo Secure Reliable Transport (SRT) se propuso como el mecanismo predeterminado e ideal para toda la distribución de video, debido a su reputación en la industria por cifrado simétrico nativo (AES-128/256) y recuperación automática de paquetes perdidos mediante ARQ (Automatic Repeat reQuest).

No obstante, la experiencia en despliegues reales de producción multicámara en redes de área local (LAN cableada gigabit) y las pruebas de laboratorio de alta concurrencia revelaron problemas estructurales profundos al usar SRT como transporte predeterminado:
1. **La trampa del doble búfer de jitter (*Double Buffer Trap*)**:
   * En la arquitectura con broker intermediario (FFmpeg publica por SRT loopback a MediaMTX, y los clientes OBS/vMix leen por SRT desde MediaMTX), existen dos búferes de fluctuación independientes en serie.
   * La biblioteca `libsrt` impone por defecto una ventana de buffering de al menos $120\text{ ms}$ en el emisor y $120\text{ ms}$ en el receptor. Incluso configurando valores de baja latencia ($50\text{ ms}$), el retardo total acumulado superaba los $150\text{ ms}$, violando el objetivo de latencia sub-50 ms.
2. **Inestabilidad del demuxer SRT en MediaMTX (`gosrt`)**:
   * Bajo bitrates elevados (1080p60 a $>6000\text{ kbps}$ con múltiples cámaras concurrentes), la implementación interna de SRT en Go utilizada por MediaMTX experimentaba pérdidas de sincronización interna, arrojando errores fatales de protocolo (`ERROR:ROGUE packet sequence`), derivando en desconexiones abruptas de clientes receptores.
3. **Complejidad innecesaria en LAN**:
   * En una red local de broadcast donde la tasa de pérdida de paquetes es prácticamente nula ($<0.01\%$), los mecanismos de retransmisión ARQ y control de congestión de SRT introducen sobrecarga computacional y retardo artificial sin aportar beneficio práctico de estabilidad.
4. **Sintaxis de URL defectuosa en receptores**:
   * La convención histórica de URLs para VLC y OBS utilizaba el formato `udp://@:<port>`, el cual generaba errores de enlace de socket (*socket bind failure*) en versiones recientes de OBS Studio y vMix. Asimismo, directivas agresivas en VLC (`:clock-jitter=0 :clock-synchro=0`) causaban congelamiento permanente de imagen ante la más mínima variación de reloj de red.

---

## 2. Factores Decisivos

* **Consecución del SLA extremo ($\le 50\text{ ms}$ P50)**: Se requiere una ruta de transporte de latencia mínima absoluta sin colas ni intermediarios.
* **Compatibilidad plug-and-play con OBS Studio y vMix**: Las URLs entregadas por la interfaz deben abrirse en OBS Studio sin requerir ajustes arcanos de red ni configuraciones manuales complejas.
* **Reproducción estable en VLC**: Comandos de lanzamiento de VLC con valores de búfer de red seguros que absorban el jitter del planificador de Windows sin congelar la imagen.
* **Claridad taxonómica para el usuario**: Desmitificar el protocolo en la interfaz gráfica: clasificar UDP Unicast como "Recomendado para Red Local (Baja Latencia Extrema)" y reclasificar SRT como "Recomendado para Internet / WAN / Enlaces Inestables".

---

## 3. Alternativas Evaluadas

### Opción A: Mantener SRT como protocolo por defecto e intentar parches de bajo nivel en `libsrt` (Descartada)
* *Ventajas*: Mantiene una sola directriz de protocolo.
* *Desventajas*: No elimina el cuello de botella intrínseco del doble búfer ni las limitaciones del broker Go en MediaMTX.

### Opción B: Forzar WebRTC WHEP como protocolo universal de distribución (Descartada)
* *Ventajas*: Latencia inferior a 30 ms directamente en navegadores.
* *Desventajas*: La fuente de navegador en OBS Studio (*Browser Source*) consume sustancialmente más recursos de GPU y CPU que una fuente multimedia nativa decodificada por hardware vía UDP (`Media Source`), resultando inviable para matrices de 4 a 8 cámaras simultáneas.

### Opción C (Elegida): Establecer UDP Unicast directo como protocolo canónico por defecto, sanear sintaxis de URLs y democionar SRT a uso en WAN
* *Ventajas*: Arquitectura zero-broker con entrega directa punto a punto. Latencia vidrio a vidrio verificada de $\sim 38.8\text{ ms}$ P50. Cero uso de memoria en servidores intermediarios. URLs limpias y compatibles con OBS (`udp://<IP>:<PORT>`) y comando VLC seguro con 300 ms de caching (`:network-caching=300`).
* *Desventajas*: UDP Unicast no ofrece retransmisión de paquetes perdidos (lo cual es prescindible en LAN gigabit cableada).

---

## 4. Decisión

Se adopta formalmente **UDP Unicast directo** como el protocolo canónico y predeterminado del sistema RTMS:

1. **Configuración y Esquema por Defecto**:
   * En la configuración base del sistema y en la plantilla `config/config.example.json`, el protocolo por defecto de toda nueva cámara es `udp` con modo `unicast` (`udp_mode = "unicast"`).
   * La interfaz gráfica (`gui/static/app.js` y `index.html`) presenta UDP Unicast con el distintivo de máxima recomendación para entornos LAN.

2. **Saneamiento de URLs de Recepción**:
   * Se elimina la sintaxis confusa `udp://@:<port>` para clientes OBS/vMix en [`core/stream_proc.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_proc.py).
   * Para OBS Studio y reproductores de producción, la URL de conexión canónica se formula estrictamente como:
     ```text
     udp://127.0.0.1:<PORT>       (para clientes en el mismo host)
     udp://<DESTINATION_IP>:<PORT> (para clientes remotos en la red LAN)
     ```
   * En VLC Media Player, el comando se calibra con búfer seguro de 300 ms y descarte de cuadros tardíos para evitar desincronización:
     ```text
     vlc.exe "udp://@:<PORT>" :network-caching=300 :drop-late-frames :skip-frames
     ```
     (Se erradican las directivas desestabilizadoras `:clock-jitter=0 :clock-synchro=0`).

3. **Democión y Contextualización de SRT**:
   * SRT permanece completamente soportado y optimizado en el motor para transmisiones a través de Internet o Wi-Fi donde la pérdida de paquetes exija cifrado y retransmisión ARQ.
   * Se ajusta la latencia interna de loopback de SRT a $10\text{ ms}$ con `tlpktdrop=1` para evitar el rechazo `ERROR:ROGUE` en gosrt.

4. **Incorporación de Transporte Raw RTP Opcional**:
   * Se añade soporte nativo para el protocolo `rtp` (`rtp://<DESTINATION_IP>:<PORT>`) con empaquetado RFC 3551 para integración directa con mesas de mezclas y receptores de broadcast profesional que requieran demuxing RTP puro.

```
+-----------------------------------------------------------------------------------+
|                            Topología de Distribución LAN                          |
+-----------------------------------------------------------------------------------+

   [DirectShow Sensor]
           |
   [FFmpeg Transcoder]
           |
           |----------------------------+
           | (Direct Zero-Broker Path)  | (WAN / Secure Path)
           v                            v
   [UDP Unicast Socket]         [MediaMTX SRT Broker]
           |                            |
    (P50: ~38.8 ms)              (P50: ~95-120 ms)
           |                            |
           v                            v
   [OBS / vMix Studio]          [Remote / Internet Studio]
   udp://<DEST_IP>:<PORT>       srt://<HOST>:<PORT>?...
```

---

## 5. Consecuencias

### Positivas
* **Consecución del Récord de Latencia**: La eliminación del intermediario MediaMTX y de las colas de libsrt permite alcanzar una latencia vidrio a vidrio de $\sim 38.8\text{ ms}$ en GPU AMD AMF y $\sim 40.8\text{ ms}$ en libx264 CPU.
* **Erradicación de Errores en OBS**: Las URLs de entrada para OBS Studio se vinculan de manera inmediata y estable sin errores de socket.
* **Cero Desconexiones de Clientes**: Se suprime el riesgo de cuelgues por desbordamiento de búfer en `gosrt`.

### Negativas
* **Requisito de IP de Destino en Unicast**: Al transmitir en Unicast a través de la LAN hacia otra estación de producción, el operador debe especificar la dirección IP del equipo receptor (simplificado mediante validación en el panel web de RTMS).
