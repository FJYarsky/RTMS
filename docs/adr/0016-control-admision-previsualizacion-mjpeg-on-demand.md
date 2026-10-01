# ADR-0016: Control de Admisión Concurrente y Streaming de Previsualización On-Demand

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Video / Concurrencia / Memoria / HTTP / Core
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS permite previsualizar en directo cualquier cámara conectada directamente en el navegador o en la ventana de la aplicación. Para no interferir con la emisión principal (que transmite hacia MediaMTX vía SRT/UDP), la previsualización se genera bajo demanda mediante extracción de cuadros JPEG o puente WebRTC WHEP.

Si múltiples usuarios abren la interfaz web desde distintos dispositivos o si un usuario abre simultáneamente los modales de vista previa de 8 cámaras, se desencadenan problemas severos de recursos:
1. **Agotamiento de Ranuras de Descodificación**: Cada subproceso FFmpeg extrayendo cuadros compite por la memoria del bus y decodificadores de hardware.
2. **Fuga de Memoria por Acumulación de Buffers HTTP**: En conexiones HTTP con streaming continuo `multipart/x-mixed-replace`, un cliente lento o una desconexión abrupta sin drenaje puede provocar que los cuadros JPEG se acumulen indefinidamente en memoria RAM.
3. **Bloqueo de Reapertura (Slots Huérfanos)**: Si el usuario cierra el modal y lo vuelve a abrir rápidamente, una comprobación ingenua de concurrencia rechaza la solicitud con HTTP 429 ("Demasiadas vistas previas simultáneas") porque el slot anterior aún no ha terminado de liberarse.

## 2. Factores Decisivos (Decision Drivers)
* **Límite Estricto de Concurrencia Global**: Restringir el número máximo de previsualizaciones activas simultáneas en el sistema (máximo 3) para salvaguardar la CPU/GPU para la transmisión de producción.
* **Reentrada Segura por Cámara (Per-Camera Reentrancy)**: Si una cámara que ya tiene un proceso de vista previa solicita una nueva sesión (reapertura de modal o refresco de navegador), el sistema debe reemplazar o reutilizar la ranura existente sin consumir una nueva ni arrojar error 429.
* **Delimitación Binaria Exacta de Cuadros JPEG (Zero-Leak Chunking)**: Localizar con precisión quirúrgica los marcadores binarios Start of Image (`0xFFD8`) y End of Image (`0xFFD9`) para evitar entregar fragmentos corruptos al navegador.
* **Límite de Seguridad en Buffer de Memoria**: Imponer un tope estricto de memoria acumulada (4 MB) por sesión de previsualización para prevenir ataques de denegación de servicio por memoria (OOM).

## 3. Opciones Consideradas
* **Opción A (Previsualización Continua en Segundo Plano para Todas las Cámaras)**: Codificar permanentemente un flujo MJPEG para cada cámara.
  - *Desventajas*: Desperdicio masivo de CPU y energía; viola el principio de diseño de 0% de uso de CPU cuando la UI no está abierta.
* **Opción B (Captura de Cuadros Únicos vía Snapshot Polling HTTP)**: El frontend solicita `/api/preview/frame` repetidamente mediante `setInterval`.
  - *Desventajas*: Tasa de cuadros baja (<5 FPS), parpadeos constantes y sobrecarga por miles de handshakes HTTP repetitivos.
* **Opción C (Streaming On-Demand `multipart/x-mixed-replace` con Semáforo Asíncrono y Extractor Binario SOI/EOI)**:
  - Generar un subproceso FFmpeg solo cuando se solicita el stream.
  - Controlar el acceso con `asyncio.Semaphore(3)` y un conjunto de cámaras activas protegido por `asyncio.Lock()`.
  - Extraer cuadros leyendo la salida estándar de FFmpeg en fragmentos y emitiendo los delimitadores exactos JPEG con tope de 4 MB.

## 4. Decisión
Se adopta la **Opción C**:
1. Se crea [`PreviewManager`](file:///C:/Users/joaqu/Desktop/RTMS/core/preview_mgr.py) en `core/preview_mgr.py`.
2. Se definen las constantes de límite de concurrencia y buffer:
   - `MAX_CONCURRENT_PREVIEWS = 3` (máximo de 3 vistas previas simultáneas).
   - `MAX_JPEG_BUFFER = 4 * 1024 * 1024` (4 MB de buffer máximo por cuadro).
3. **Algoritmo de Admisión y Reentrada**:
   - `acquire_slot(identifier)` evalúa si `identifier` (ruta o ID de la cámara) ya se encuentra en `_active_camera_previews`.
   - Si ya está registrado, retorna `True` inmediatamente, permitiendo que la nueva conexión asuma el control del stream sin agotar el semáforo global.
   - Si es una cámara nueva, intenta adquirir `_preview_semaphore` con un timeout de 10 ms (`asyncio.wait_for`). Si el semáforo está agotado, rechaza limpiamente la petición.
4. **Extractor de Cuadros JPEG Robusto**:
   - Se procesa el flujo binario de `stdout` buscando el marcador SOI: `b"\xff\xd8"` y el marcador EOI: `b"\xff\xd9"`.
   - Al encontrar el par completo, se extrae el cuadro exacto, se formatea como bloque HTTP:
     ```text
     --frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len}\r\n\r\n{bytes}\r\n
     ```
     y se emite al generador asíncrono.
   - Si el buffer acumulado supera `MAX_JPEG_BUFFER` (4 MB) sin encontrar un fin de imagen válido (debido a flujo corrupto de la cámara), el buffer se trunca inmediatamente y se descarta el fragmento corrupto, evitando el consumo descontrolado de memoria.
5. Al desconectarse el cliente HTTP, el generador asíncrono finaliza, liquidando el subproceso FFmpeg y liberando el slot del semáforo mediante `release_slot()`.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Protección Total de los Recursos de Producción**: La visualización nunca puede saturar el equipo, ya que un máximo de 3 cámaras pueden previsualizarse a la vez.
* **Experiencia de Usuario Fluida**: Reaperturas rápidas de ventanas no provocan falsos positivos de saturación (cero errores 429 innecesarios).
* **Integridad de Memoria**: La cota de 4 MB por buffer impide fugas de memoria o acumulación desmedida de bytes ante caídas de red.
* **Cero Carga en Reposo**: Cuando no hay previsualizaciones abiertas, el gestor tiene exactamente cero subprocesos en ejecución.

### Consecuencias Negativas / Limitaciones (-)
* Si un cuarto operador intenta previsualizar una cámara distinta mientras 3 ya están activas, recibirá un mensaje de límite de concurrencia alcanzado hasta que una de las sesiones activas se cierre.

## 6. Validación y Cumplimiento
* Pruebas del gestor de vistas previas y adquisición de slots en [`tests/test_preview.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_preview.py).
* Auditoría de liberación de procesos y límites de memoria en [`tests/test_audit_preview.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_preview.py).
