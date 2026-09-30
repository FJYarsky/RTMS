# ADR-0001: Adopción de MediaMTX como Broker Central y Servidor de Streaming

* **Fecha**: 2026-09-15
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Core / Red / Streaming
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS requiere retransmitir flujos multicámara hacia múltiples clientes concurrentes (OBS Studio, reproductores VLC, navegadores web modernos, suites de producción de televisión) sin sobrecargar los codificadores de captura local y asegurando latencias por debajo de 500 milisegundos.

Si cada cliente conectara directamente contra el proceso de captura de la cámara (FFmpeg DirectShow), se requeriría una instancia de codificación dedicada por cliente, saturando inmediatamente la CPU y las ranuras de codificación por hardware (NVENC/QSV) del sistema.

## 2. Factores Decisivos (Decision Drivers)
* **Multiplexación 1-a-N**: Una sola sesión de codificación local por cámara debe servir a decenas de clientes en red.
* **Soporte Protocolar Múltiple**: SRT (Secure Reliable Transport), WebRTC (WHEP/WHIP), RTSP y RTMP simultáneos.
* **Ultra-Baja Latencia**: Capacidad de conmutación de paquetes sin re-codificación con latencias agregadas menores a 20 ms.
* **Autonomía y Portabilidad**: Debe funcionar en entornos locales (Zero-Config) y empaquetarse en binario independiente para Windows sin runtime externos (Node.js, Docker o JVM).
* **Control Programático**: API REST para inspección de rutas activas y autenticación dinámica.

## 3. Opciones Consideradas
* **Opción A (Nginx con módulo RTMP)**: Tradicional pero con latencias elevadas (>1500 ms) y soporte experimental deficiente para SRT y WebRTC nativo.
* **Opción B (Servidor WebRTC custom en Python con aiortc)**: Elevado consumo de CPU en multiplexación multicámara y problemas de rendimiento en Windows con más de 4 flujos en alta resolución.
* **Opción C (MediaMTX - antes rtsp-simple-server)**: Servidor de medios de alto rendimiento escrito en Go, mono-binario, sin dependencias, con soporte nativo de primera clase para SRT, WebRTC, RTSP y RTMP.

## 4. Decisión
Se adopta **MediaMTX** como el broker de streaming central y orquestador de paquetes de RTMS.
1. FFmpeg actúa como cliente de publicación (`mode=caller`) empujando el flujo codificado hacia MediaMTX a través de sockets locales SRT (`srt://127.0.0.1:8890?streamid=publish:{cam_id}`).
2. MediaMTX gestiona la tabla de enrutamiento y retransmite hacia clientes externos bajo demanda (OBS, VLC, WebRTC WHEP en navegadores).
3. Se implementa el gestor [`core/mediamtx_mgr.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/mediamtx_mgr.py) para controlar el ciclo de vida del subproceso `mediamtx.exe`, monitorear su salud y arrancar bajo demanda.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Ahorro Masivo de Hardware**: Solo 1 proceso de captura/codificación por cámara física, independientemente de la cantidad de espectadores.
* **Flexibilidad Protocolar**: Permite a OBS consumir SRT con recuperación de paquetes ARQ, mientras que un navegador web visualiza en tiempo real vía WebRTC WHEP sobre el mismo stream.
* **Estabilidad y Consumo**: Menos de 30 MB de RAM y menos de 1% de CPU para gestionar 8 flujos de video 1080p concurrentes.

### Consecuencias Negativas / Limitaciones (-)
* Se requiere distribuir el binario precompilado `bin/mediamtx.exe`.
* Se debe sincronizar el ciclo de vida del proceso para evitar puertos huérfanos tras un cierre abrupto (mitigado con `job objects` de Windows y verificaciones en `PowerManager`).

## 6. Validación y Cumplimiento
* Certificado en [`tests/test_vlc_integration.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_vlc_integration.py) y en [`tests/test_e2e_complete_pipeline.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_e2e_complete_pipeline.py).
* Verificación automatizada de sockets y ciclo de vida vía [`scripts/e2e_pipeline_tester.py --all`](file:///C:/Users/joaqu/Desktop/RTMS/scripts/e2e_pipeline_tester.py).
