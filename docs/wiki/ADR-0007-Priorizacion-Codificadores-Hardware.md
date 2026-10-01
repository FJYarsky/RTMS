# ADR-0007: Detección y Priorización de Codificadores GPU con Fallback Resiliente

* **Fecha**: 2026-09-17
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Hardware / Silicio / Rendimiento / Video
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
La compresión de video en tiempo real para múltiples cámaras a 1080p @ 30/60 FPS requiere una cantidad sustancial de potencia de cómputo. La codificación por software en CPU mediante `libx264` con perfiles de baja latencia consume entre un 15% y un 35% de CPU por cámara, saturando rápidamente procesadores convencionales cuando se superan las 3 señales simultáneas.

La mayoría de las computadoras modernas disponen de silicio dedicado para codificación de video por hardware (ASICs en GPUs NVIDIA, Intel, AMD o Apple Silicon), los cuales pueden codificar múltiples flujos a latencia sub-cuadro con menos de 1% de carga sobre la CPU general.

## 2. Factores Decisivos (Decision Drivers)
* **Descarga Total de la CPU**: Permitir la operación fluida de 8 cámaras en paralelo en una sola estación de trabajo.
* **Soporte Multi-Proveedor Transparente**: Detección automática de aceleración de hardware disponible sin requerir selección manual por parte del operador.
* **Tolerancia a Fallos y Fallback Automático**: Si una GPU rechaza la codificación (por ejemplo, por alcanzar el límite de sesiones concurrentes de NVENC o por un driver corrupto), el flujo no debe morir, sino degradarse de inmediato a codificación por CPU.

## 3. Opciones Consideradas
* **Opción A (Forzar codificación por software libx264)**: Universal y predecible, pero con alto consumo de CPU y límites severos en la cantidad de cámaras concurrentes.
* **Opción B (Soporte exclusivo para NVIDIA NVENC)**: Excelente rendimiento en GPUs dedicadas pero inutilizable en laptops con gráficos integrados Intel o GPUs AMD Radeon.
* **Opción C (Matriz Heurística Multi-Vendor con Fallback Dinámico en 2 Etapas)**: Detección escalonada de hardware y degradación automática a CPU en caso de rechazo del codificador.

## 4. Decisión
Se implementa la **Opción C**:
1. En ``core/hardware.py``, se define la jerarquía estricta de aceleración:
   - **NVIDIA**: `h264_nvenc` / `hevc_nvenc` / `av1_nvenc` (con presets ultra-baja latencia `llhp` / `p1`, `zerolatency=1`).
   - **Intel**: `h264_qsv` / `hevc_qsv` (preset `veryfast`, `async_depth=1`).
   - **AMD**: `h264_amf` / `hevc_amf` (usage `lowlatency`).
   - **Apple Silicon / macOS**: `h264_videotoolbox`.
   - **Fallback Universal (CPU)**: `libx264` (preset `ultrafast`, tune `zerolatency`).
2. En ``core/stream_manager.py``:
   - Al iniciar un stream, se intenta el codificador por hardware detectado.
   - Si FFmpeg sale con código de error en los primeros 2 segundos (típico fallo de sesión NVENC superada o falta de memoria VRAM), el gestor conmuta de forma automática a `force_cpu=True`, reiniciando el flujo con `libx264` sin requerir reinicio de la aplicación.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Escalabilidad Multicámara**: Permite procesar de 4 a 8 cámaras en tarjetas gráficas comunes de consumo (RTX 3060/4060 o gráficos Intel Iris Xe).
* **Alta Disponibilidad**: El usuario nunca se queda sin señal de video; a lo sumo observará un mayor uso de CPU temporal mientras dure el fallback.
* **Presets Optimizados**: Cada codificador de silicio recibe los flags exactos de su fabricante para eliminar buffers internos (`zerolatency`).

### Consecuencias Negativas / Limitaciones (-)
* Los controladores de GPU desactualizados pueden causar comportamientos inesperados; se incorporó la detección de versión de driver en ``core/doctor.py``.

## 6. Validación y Cumplimiento
* Pruebas de detección y sintaxis de línea de comandos en ``tests/test_hardware_parser.py`` y ``tests/test_hardware_concurrency.py``.
* Verificado con GPU física NVIDIA NVENC a 30.67 FPS continuos en ``scripts/e2e_pipeline_tester.py``.
