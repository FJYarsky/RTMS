# ADR-0005: Distribución UDP Multicast (239.255.0.x) y Unicast de Baja Latencia

* **Fecha**: 2026-09-18
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Red / Streaming / Protocolos
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
Si bien SRT es el protocolo preferido por su confiabilidad sobre redes con pérdida de paquetes (gracias a sus buffers de retransmisión ARQ), en entornos de red local controlada (LAN Ethernet Gigabit o redes de estudio) muchos operadores exigen latencias absolutas mínimas (< 150 ms) y consumo nulo de overhead de retransmisión.

Asimismo, en redes LAN con múltiples receptores simultáneos, el protocolo Unicast multiplica el tráfico por el número de receptores, requiriendo una alternativa Multicast para distribuir el flujo a todos los puestos de control sin multiplicar el ancho de banda.

## 2. Factores Decisivos (Decision Drivers)
* **Latencia Ultra-Baja**: Alcanzar retardos inferiores a 150 ms entre captura física y despliegue en pantalla.
* **Eficiencia de Ancho de Banda LAN**: Transmisión 1-a-N en red local mediante Multicast IGMP.
* **Aislamiento de Flujos**: Evitar colisiones de direcciones o puertos entre múltiples cámaras activas en el mismo segmento de red.
* **Compatibilidad de Clientes**: Configuración estándar para OBS Studio y VLC Media Player.

## 3. Opciones Consideradas
* **Opción A (UDP Unicast a puerto fijo con socket binding global)**: Simple, pero solo permite 1 receptor por cámara y colisiona si dos cámaras usan el mismo puerto.
* **Opción B (RTSP sobre UDP interleaved)**: Añade la sobrecarga del handshake RTSP de control y negociación SDP previa.
* **Opción C (Mapeo inyectivo UDP Multicast 239.255.0.x + Unicast local con buffer no bloqueante)**: Mapear el identificador numérico o puerto de cada cámara a una IP de multicast administrativa clase D (`239.255.0.{cam_idx}`), con URLs específicas para receptores.

## 4. Decisión
Se implementa la **Opción C**:
1. **Multicast LAN**:
   - Cada cámara con protocolo `udp` y modo `multicast` emite hacia una IP administrativa de clase D derivada de su puerto: `239.255.0.{(port % 250) + 1}:{port}`.
   - En ``core/command_builder.py``, se inyectan los parámetros `pkt_size=1316&buffer_size=65536&ttl=5`.
   - Los clientes VLC y OBS conectan usando la sintaxis estándar `udp://@239.255.0.X:PORT`.
2. **Unicast Localhost**:
   - Para conexiones locales directas en la misma máquina, se utiliza `udp://127.0.0.1:{port}?pkt_size=1316&buffer_size=65536`.
   - Para recepción en VLC se genera `udp://@:{port}` y para FFmpeg `udp://127.0.0.1:{port}?buffer_size=65536&overrun_nonfatal=1`.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Latencia Mínima Absoluta**: Medida empíricamente en ~121 ms (contra ~447 ms de SRT), ideal para retorno de teleprompter o monitor de piso.
* **Cero Carga Adicional por Espectador en Multicast**: 1 o 50 receptores en la misma LAN consumen exactamente el mismo ancho de banda del switch.

### Consecuencias Negativas / Limitaciones (-)
* **Sensibilidad a Pérdida de Paquetes**: Al no contar con retransmisión ARQ, las redes Wi-Fi con interferencias pueden presentar artefactos o macrobloques (mitigado con `nobuffer+discardcorrupt` y `overrun_nonfatal=1`).

## 6. Validación y Cumplimiento
* Certificado en ``tests/test_vlc_integration.py``.
* Verificado en el benchmark E2E: ``core/pipeline_verifier.py`` obteniendo 121.7 ms de ping medio con 0 cuadros caídos.
