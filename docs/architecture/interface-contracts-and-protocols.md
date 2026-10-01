# Contratos de Interfaz, APIs y Protocolos de Red de RTMS

* **Versión del Sistema**: RTMS v2.8.0+
* **Autor**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área**: API REST / WebSockets / Protocolos de Red / Streaming / Seguridad

---

## 1. Contratos de la API REST (FastAPI)

Todos los endpoints mutantes y administrativos requieren autenticación mediante la cabecera `X-RTMS-Token` o la cookie de sesión HttpOnly `rtms_session`. Queda categóricamente prohibido el paso de tokens mediante parámetros de consulta (*query parameters*), retornando `HTTP 403 Forbidden`.

### 1.1 Catálogo de Endpoints de Control

| Método | Endpoint | Cabeceras Requeridas | Parámetros / Body (JSON) | Códigos HTTP | Descripción |
| :---: | :--- | :--- | :--- | :---: | :--- |
| `GET` | `/api/health` | Ninguna | Ninguno | `200` | Health check del servidor y estado de MediaMTX. |
| `GET` | `/api/system/devices` | `X-RTMS-Token` | `?force_refresh=bool` | `200, 403` | Retorna lista de dispositivos DirectShow físicos. |
| `GET` | `/api/streams` | `X-RTMS-Token` | Ninguno | `200, 403` | Retorna el inventario consolidado y estados FSM de cámaras. |
| `POST` | `/api/streams/action` | `X-RTMS-Token` | `StreamAction` (`device_path`, `action`) | `200, 400, 403` | Inicia, detiene o reinicia un flujo de cámara. |
| `POST` | `/api/streams/stop-all`| `X-RTMS-Token` | Ninguno | `200, 403` | Detiene todas las transmisiones activas. |
| `GET` | `/api/config` | `X-RTMS-Token` | Ninguno | `200, 403` | Obtiene la configuración completa del sistema. |
| `POST` | `/api/config/camera` | `X-RTMS-Token` | `CameraConfigUpdate` | `200, 422, 403` | Modifica parámetros de resolución, bitrate, encoder o SRT. |
| `POST` | `/api/preview/ticket`| `X-RTMS-Token` | `PreviewTicketRequest` (`device_path`, `ttl_seconds`) | `200, 403` | Genera un token efímero de un solo uso para streaming. |
| `GET` | `/api/preview/mjpeg/{cam_id}` | Ninguna | `?ticket={token_urlsafe}` | `200, 403, 429` | Flujo continuo `multipart/x-mixed-replace` de cuadros JPEG. |
| `POST` | `/api/preview/ffplay`| `X-RTMS-Token` | `{"url": "srt://..."}` | `200, 400, 403` | Lanza reproductor de baja latencia nativo FFplay. |
| `POST` | `/api/system/shutdown`| `X-RTMS-Token` | `SystemShutdownRequest` (`force`) | `200, 403` | Ejecuta el protocolo de apagado ordenado del sistema. |

### 1.2 Esquemas de Validación (Pydantic Models)

#### Modificación de Configuración de Cámara (`CameraConfigUpdate`)
```json
{
  "device_path": "@device_pnp_\\\\?\\usb#vid_046d&pid_0825...",
  "resolution": "1080p",
  "fps": 30,
  "bitrate": 4500,
  "protocol": "srt",
  "encoder": "h264_nvenc",
  "srt_latency": 50,
  "srt_passphrase": "clave_segura_produccion_2026",
  "secret_action": "set",
  "zerolatency": true,
  "auto_start": true,
  "udp_mode": "multicast"
}
```
* **Restricción `srt_passphrase`**: Si se provee, debe cumplir con la longitud de 10 a 79 caracteres impuesta por el estándar `libsrt`.

---

## 2. Protocolo WebSocket de Telemetría a 10 Hz (`/api/ws/telemetry`)

El canal WebSocket provee un flujo bidireccional continuo de datos y eventos en tiempo real.

### 2.1 Esquema de Mensaje Ticker (Métricas Periódicas a 10 Hz)
Emitido 10 veces por segundo cuando hay clientes conectados.

```json
{
  "type": "telemetry",
  "timestamp": 1790875200.123,
  "host": {
    "cpu_percent": 14.2,
    "memory_used_mb": 4210.5,
    "memory_total_mb": 16384.0,
    "memory_percent": 25.7,
    "net_sent_kbps": 9450.2,
    "net_recv_kbps": 320.1,
    "gpu": {
      "load_percent": 18.0,
      "memory_used_mb": 840.0,
      "memory_total_mb": 6144.0,
      "temperature_c": 52.0
    }
  },
  "streams": [
    {
      "device_path": "@device_pnp_\\\\?\\usb#vid_046d&pid_0825...",
      "friendly_name": "Logitech HD Webcam C270",
      "state": "running",
      "fps": 30.0,
      "bitrate_kbps": 4480.5,
      "speed": "1.00x",
      "dropped_frames": 0,
      "total_frames": 18450
    }
  ],
  "summary": {
    "active_streams": 1,
    "total_streams": 3,
    "total_bitrate_kbps": 4480.5
  }
}
```

### 2.2 Esquema de Eventos Reactivos Discretos
Emitido instantáneamente ante transiciones de estado, desconexión de hardware o alertas.

```json
{
  "type": "event",
  "event": "stream_state_changed",
  "data": {
    "device_path": "@device_pnp_\\\\?\\usb#vid_046d&pid_0825...",
    "previous_state": "starting",
    "new_state": "running"
  },
  "timestamp": 1790875200.150
}
```

---

## 3. Especificación del Protocolo de Red SRT (Secure Reliable Transport)

### 3.1 Canal de Ingesta (FFmpeg Publisher $\rightarrow$ MediaMTX Broker)
* **Modo de Conexión**: `mode=caller` (FFmpeg empuja el flujo al broker local).
* **Dirección de Enlace**: `srt://127.0.0.1:8890?streamid=publish:{cam_id}&...`
* **Parámetros de Capa de Transporte**:
  - `latency = 50000` ($\mu\text{s}$, 50 ms en zerolatency).
  - `tlpktdrop = 1` (incondicional en caller: descarta paquetes tardíos para evitar acumular buffer).
  - `transtype = live`
  - `sndbuf = 65536` bytes, `rcvbuf = 65536` bytes.
  - `pkt_size = 1316` bytes (exactamente 7 paquetes MPEG-TS de 188 bytes).
  - `smoother` = deshabilitado en modo caller para erradicar retardo artificial de pacing.

### 3.2 Canal de Distribución y Lectura (MediaMTX Broker $\rightarrow$ OBS / vMix / VLC)
* **Modo de Conexión**: `mode=listener` (MediaMTX escucha conexiones entrantes de clientes).
* **URL Canónica Generada**:
  `srt://{host}:8890?streamid=read:{cam_id}&latency=50000&rcvbuf=65536&tlpktdrop=1&passphrase={secret}`
* **Cifrado Simétrico**: AES-128 nativo con derivación de clave por contraseña (`pbkeylen=16`).

---

## 4. Especificación del Protocolo de Red UDP Multicast y Unicast

### 4.2 Mapeo Canónico de Direcciones Multicast
Para evitar colisiones entre múltiples cámaras dentro del segmento LAN, RTMS calcula de forma determinista la IP del grupo multicast en base al puerto de transmisión:

$$P \in [9000, 9200] \implies \mathrm{IP}_{\mathrm{multicast}} = \texttt{239.255.0.} \left( (P - 9000) + 1 \right)$$
$$P \notin [9000, 9200] \implies \mathrm{IP}_{\mathrm{multicast}} = \texttt{239.255.0.} \left( ((P - 1024) \bmod 250) + 1 \right)$$

* **Parámetros del Socket Multicast**:
  - `pkt_size=1316`: Tamaño óptimo de payload MTU.
  - `ttl=16`: Tiempo de vida restringido a la red de producción local (evita escape hacia WAN).
  - `buffer_size=65536`: Buffer mínimo para evitar acumulación de latencia.
  - `overrun_nonfatal=1`: Continuar transmisión si el buffer se satura temporalmente.
  - `fifo_size=5000`: Cola interna de paquetes en FFmpeg.
* **Sintaxis de Reproducción en VLC Player**:
  - Multicast: `vlc.exe "udp://@239.255.0.x:{port}" :network-caching=50 :clock-jitter=0 :clock-synchro=0`
  - Unicast Local: `vlc.exe "udp://@:{port}" :network-caching=50 :clock-jitter=0 :clock-synchro=0`

---

## 5. Protocolo de Tickets Efímeros de Previsualización

Para autorizar solicitudes de imágenes o flujos sin cabeceras HTTP personalizadas:
1. **Generación**: El cliente envía `POST /api/preview/ticket` con cabecera `X-RTMS-Token`. El backend responde con un token urlsafe de 32 bytes (`ticket`).
2. **Asociación**: El token queda ligado a la ruta de la cámara y a una marca de tiempo de expiración:
   $$t_{\mathrm{exp}} = t_{\mathrm{actual}} + \Delta t_{\mathrm{ttl}} \quad (\text{con } \Delta t_{\mathrm{ttl}} = 60\text{ s por defecto})$$
   donde el tiempo de vida en segundos se configura mediante el parámetro `ttl_seconds`.
3. **Consumo Atómico**: Al recibir `GET /api/preview/mjpeg/{cam_id}?ticket={ticket}`, la función `consume_ticket()` extrae y borra atómicamente el ticket bajo `threading.Lock()`. Cualquier petición posterior con el mismo ticket es rechazada con `HTTP 403`.
4. **Desalojo por Capacidad**: Máximo 100 tickets simultáneos en memoria. Al alcanzar el límite, el ticket más antiguo es purgado automáticamente.
