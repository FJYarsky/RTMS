# ADR-0003: Cifrado Simétrico AES-128 con Passphrase y Autenticación en SRT

* **Fecha**: 2026-09-20
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Seguridad / Red / Streaming
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
En eventos de transmisión en vivo, producción multicámara y entornos corporativos o educativos, las señales de video transmitidas por la red local o WAN no deben ser interceptables ni visualizables por dispositivos o usuarios no autorizados.

El protocolo SRT cuenta con capacidades nativas de cifrado simétrico mediante el estándar AES (Advanced Encryption Standard) con longitudes de clave de 128, 192 o 256 bits, derivadas a partir de una contraseña compartida (*passphrase*). Se requería una implementación homogénea tanto en el proceso emisor (FFmpeg) como en el servidor distribuidor (MediaMTX) y en los clientes finales (OBS Studio, VLC Player).

## 2. Factores Decisivos (Decision Drivers)
* **Confidencialidad Extremo a Extremo**: El flujo de video y audio debe viajar cifrado por el medio de red.
* **Rechazo Estricto de Conexiones No Autorizadas**: Si un receptor intenta conectarse sin contraseña o con una contraseña incorrecta, el handshake SRT debe ser denegado de inmediato.
* **Bajo Impacto en Latencia y CPU**: La sobrecarga criptográfica no debe incrementar la latencia ni requerir aceleración criptográfica dedicada inalcanzable en CPUs comunes.
* **Compatibilidad de Clientes**: Clientes estándar de la industria (OBS Studio, VLC con módulo `access_srt`) deben poder reproducir el flujo simplemente suministrando el parámetro `passphrase`.

## 3. Opciones Consideradas
* **Opción A (Túneles VPN / WireGuard / IPsec a nivel de red)**: Seguro pero requiere configuración de infraestructura de red compleja, permisos de administrador y añade sobrecarga en el empaquetado.
* **Opción B (Cifrado en capa de aplicación TLS sobre WebRTC)**: Seguro, pero WebRTC tiene mayor complejidad de señalización para producción multicámara en OBS Studio comparado con SRT.
* **Opción C (Cifrado nativo de capa de transporte SRT con AES-128)**: Utilizar el estándar nativo de la SRT Alliance, configurando `passphrase` y `pbkeylen=16` (128 bits) o `32` (256 bits).

## 4. Decisión
Se adopta la **Opción C** con cifrado **AES-128**:
1. En la configuración de cámara (``core/config_mgr.py``), se añade el campo `srt_passphrase: Optional[str]`.
2. En ``core/command_builder.py``, si se define una clave, FFmpeg publica con los parámetros:
   `passphrase={secret}&pbkeylen=16`
3. En ``core/mediamtx_mgr.py``, se utiliza la API REST de MediaMTX para registrar dinámicamente la ruta con `srtPassphrase: secret`, asegurando que MediaMTX exija la misma contraseña para lectura (`mode=listener`).
4. En ``core/stream_proc.py``, el generador de URLs para OBS y VLC inyecta `&passphrase={secret}`.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Seguridad Robusta**: Todo el tráfico UDP subyacente de SRT está cifrado mediante AES-128 en modo CTR/GCM nativo de `libsrt`.
* **Aislamiento por Cámara**: Cada cámara o señal puede tener su propia contraseña independiente.
* **Transparencia para OBS Studio**: Los operadores de streaming solo deben pegar la URL generada en la interfaz de RTMS.

### Consecuencias Negativas / Limitaciones (-)
* Las contraseñas de SRT en la especificación deben tener entre 10 y 79 caracteres. Se añadió validación en los esquemas Pydantic (``core/schemas.py``) para alertar al usuario si la clave no cumple con la longitud mínima requerida por `libsrt`.

## 6. Validación y Cumplimiento
* Pruebas automatizadas en ``tests/test_audit_security.py`` y ``tests/test_vlc_integration.py``.
* Verificación E2E de conexión autorizada y rechazo de contraseña errónea en ``core/pipeline_verifier.py``.
