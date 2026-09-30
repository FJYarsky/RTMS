# ADR-0004: Verificador Ineludible E2E y Medición Matemática de Ping Óptico

* **Fecha**: 2026-09-30
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: QA / Telemetría / Benchmark / Diagnóstico
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
Históricamente, diagnosticar retrasos de video (latencia) y verificar si la cadena completa de emisión (Captura -> Codificación -> Protocolo -> MediaMTX -> Receptor) funcionaba correctamente dependía de inspección visual subjetiva (poner un cronómetro frente a una cámara física y filmar un monitor) o pruebas manuales en OBS Studio y VLC.

Este enfoque adolece de problemas críticos:
1. No es reproducible en pipelines de integración continua (CI/CD) ni en entornos sin operador humano.
2. Los relojes filmados por sensores ópticos sufren distorsión de obturación (*rolling shutter*), desenfoque de movimiento (*motion blur*) y compresión con pérdida de OCR.
3. No permitía certificar si un problema de retardo se originaba en el buffer del reproductor cliente, en la red o en el proceso emisor.

## 2. Factores Decisivos (Decision Drivers)
* **Medición Determinista y Sub-Milisegundo**: Capacidad de calcular el retardo numérico exacto en milisegundos con métricas estadísticas (mínimo, máximo, promedio, jitter y percentil 95).
* **Inmunidad a la Compresión DCT / H.264**: El método de codificación del tiempo no debe degradarse por la cuantización con pérdida del códec de video.
* **Detección Automática de Anomalías**: Detección de cuadros caídos (*frame drops*), congelamientos (*freezes*), repeticiones y corrupción de datos.
* **Cámara Virtual Sintética Integrada**: Capacidad de emitir flujos de prueba sin necesidad de contar con una cámara web física conectada.

## 3. Opciones Consideradas
* **Opción A (OCR Tradicional con Tesseract sobre imagen capturada)**: Intentar leer los números del reloj en pantalla. Descartado: alto consumo de CPU, latencia propia del motor OCR y errores de reconocimiento causados por macrobloques DCT de compresión.
* **Opción B (Metadatos SEI en el flujo H.264)**: Incrustar el timestamp en mensajes SEI (Supplemental Enhancement Information). Descartado porque muchos reproductores y demuxers estándar descartan los mensajes SEI no estándar.
* **Opción C (Cabecera Óptica Binaria por Bloques + Reloj Renderizado)**: Dibujar en la parte superior de cada cuadro una secuencia de bloques binarios de alto contraste (16x16 píxeles) con un preámbulo Barker y el timestamp Epoch codificado en binario, decodificable mediante muestreo de centroides sin OCR.

## 4. Decisión
Se implementa la **Opción C** como el estándar de verificación oficial de RTMS:
1. En [`core/pipeline_verifier.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/pipeline_verifier.py):
   - **`SyntheticClockGenerator`**: Renderiza video RGB de alta fidelidad a 30 FPS con el reloj en texto legible para humanos y la cabecera óptica binaria de 72 bloques (8 bits Barker + 48 bits Epoch ms + 16 bits secuencia).
   - **`VirtualClockStreamer`**: Inyecta los cuadros sintéticos directamente en FFmpeg a tasa constante (CFR) para transmitirlos por SRT o UDP.
   - **`decode_burned_in_header`**: Lee los píxeles del stream decodificado por un receptor de prueba, muestrea el centroide de cada celda y extrae el timestamp original `t_origen`.
   - **Cálculo de Ping**: `Ping = t_recepción - t_origen`.
2. Se expone como herramienta CLI permanente en [`scripts/e2e_pipeline_tester.py`](file:///C:/Users/joaqu/Desktop/RTMS/scripts/e2e_pipeline_tester.py) con soporte para `--all`, `--ping`, `--obs-mode`, `--json` y `--markdown`.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Diagnóstico Ineludible**: Permite comprobar en menos de 10 segundos si SRT, UDP o WebRTC están funcionando al 100% en una máquina dada.
* **Precisión Matemática**: Permite medir empíricamente que UDP Unicast alcanza ~120 ms y SRT ~450 ms en condiciones óptimas locales.
* **Modo OBS Interactivo**: Permite al usuario iniciar `--obs-mode` para ver la cámara virtual con el reloj en su propia instalación de OBS y comprobar su configuración de latencia.

### Consecuencias Negativas / Limitaciones (-)
* La generación de cuadros sintéticos en CPU utiliza PIL (`Pillow`), requiriendo ~2-3% de CPU durante la ejecución de la prueba.

## 6. Validación y Cumplimiento
* Integrado en la suite de pruebas unitarias y E2E: [`tests/test_e2e_complete_pipeline.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_e2e_complete_pipeline.py).
* Certificado en ejecución real: 9/9 pruebas exitosas.
