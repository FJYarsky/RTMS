# RFC-0001: Especificación del Protocolo de Verificación E2E y Benchmark Óptico de Ping

* **Estado**: Implementado
* **Fecha de Creación**: 2026-09-30
* **Última Actualización**: 2026-09-30
* **Autor(es)**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área / Componente**: Core / Testing / Video Analytics / Benchmark

---

## 1. Resumen Ejecutivo (Abstract)
Este documento especifica el protocolo y la arquitectura de verificación de extremo a extremo (E2E), generación de señal sintética y telemetría óptica de RTMS. Define una técnica determinista basada en una cabecera óptica binaria de 72 bloques por cuadro que permite calcular la latencia absoluta (ping) de extremo a extremo en milisegundos con precisión sub-milisegundo, inmune a la compresión DCT con pérdida de códecs H.264/HEVC/AV1, además de detectar cuadros perdidos, cuadros duplicados y congelamientos del pipeline.

---

## 2. Motivación y Casos de Uso
La verificación de latencia en sistemas de video en tiempo real suele verse obstaculizada por:
1. **Inconsistencia de Sensores Físicos**: Grabar una pantalla externa añade la latencia de captura del sensor, el tiempo de respuesta del panel y artefactos de obturación (*rolling shutter*).
2. **Degradación de OCR por Compresión**: Los caracteres alfanuméricos pequeños sufren desenfoque y artefactos de bloques (*ringing / blocking*) bajo perfiles de codificación rápida (`ultrafast`, bitrate bajo), provocando lecturas erróneas.
3. **Falta de Automatización**: No existía una forma de validar en CI o diagnósticos locales si un cambio en los argumentos de FFmpeg o MediaMTX degradaba la latencia o provocaba caída de paquetes.

---

## 3. Especificación Detallada del Diseño

### 3.1 Estructura de la Cabecera Óptica Binaria
En el borde superior de cada cuadro de video (coordenadas Y: 12 a 28 px) se renderiza una franja horizontal de 72 celdas rectangulares de 16x16 píxeles cada una:

```text
+------------------------------------------------------------------------------------+
|  0..7: Barker (8b)  |     8..55: Epoch ms (48b)      |    56..71: Seq Idx (16b)    |
|  [1 0 1 0 1 1 0 0]  | [0 0 ... 1 0 1 1 0 1 0 0 1 1]  |    [0 0 ... 0 1 0 1]        |
+------------------------------------------------------------------------------------+
```

* **Preámbulo Barker Extendido (8 bits)**: Patrón binario constante `[1, 0, 1, 0, 1, 1, 0, 0]`. Se utiliza para correlación cruzada y rechazo instantáneo de cuadros negros, incompletos o corruptos.
* **Marca de Tiempo Epoch Unix (48 bits)**: Entero sin signo de 48 bits que representa los milisegundos transcurridos desde el Unix Epoch (`time.time() * 1000`). Cubre un rango de más de 8,000 años con resolución de 1 ms.
* **Índice Secuencial de Cuadro (16 bits)**: Contador incremental (`0` a `65535`) que se reinicia cíclicamente. Permite detectar cuadros omitidos (*frame drops*) o cuadros repetidos (*pipeline freeze / stutter*).

### 3.2 Representación Visual y Algoritmo de Muestreo de Centroides
Cada bit se dibuja como un bloque monocromático de alto contraste:
* Bit `1`: Blanco puro `RGB(255, 255, 255)`.
* Bit `0`: Negro puro `RGB(0, 0, 0)`.
* Borde de aislamiento: Fondo negro de 2 píxeles rodeando toda la cabecera para evitar contaminación lumínica del fondo.

El decodificador en ``core/pipeline_verifier.py`` no realiza OCR ni transformadas de Hough. En su lugar, calcula el **centroide geométrico** exacto de cada celda:
$$X_i = 10 + (i \cdot S_{\mathrm{block}}) + \left(\frac{S_{\mathrm{block}}}{2}\right)$$
$$Y = Y_{\mathrm{barcode}} + \left(\frac{S_{\mathrm{block}}}{2}\right)$$
donde el tamaño de celda es $S_{\mathrm{block}} = 10\text{ px}$ (`BLOCK_SIZE`) y la posición vertical es $Y_{\mathrm{barcode}} = 10\text{ px}$ (`BARCODE_Y_POS`).

Para cada centroide $(X_i, Y)$, se extrae el promedio de los canales de color del buffer de píxeles decodificados en memoria (`rgb24`):
$$\text{Luminancia}_i = \frac{R(X_i, Y) + G(X_i, Y) + B(X_i, Y)}{3}$$
$$\text{Bit}_i = \begin{cases} 1 & \text{si } \text{Luminancia}_i > 128 \\ 0 & \text{si } \text{Luminancia}_i \le 128 \end{cases}$$

### 3.3 Fórmulas Matemáticas de Ping, Jitter y Fiabilidad
Para una secuencia de $N$ cuadros decodificados exitosamente en los instantes de recepción $t_{\text{rx}, k}$:
1. **Latencia / Ping Instantáneo**:
   $$P_k = t_{\text{rx}, k} - t_{\text{tx}, k}$$
2. **Ping Promedio**:
   $$\bar{P} = \frac{1}{N} \sum_{k=1}^N P_k$$
3. **Jitter (Desviación Estándar de Latencia)**:
   $$J = \sqrt{\frac{1}{N-1} \sum_{k=1}^N (P_k - \bar{P})^2}$$
4. **Detección de Cuadros Perdidos**:
   $$\text{Drops} = \sum_{k=2}^N \max(0, (\text{Seq}_k - \text{Seq}_{k-1} - 1))$$

---

## 4. Consideraciones de Rendimiento
* **Tasa de Cuadros (CFR)**: El generador inyecta cuadros a una cadencia constante garantizada de 30 FPS mediante un temporizador de alta resolución (`time.perf_counter`).
* **Carga de CPU**: Renderizado de cada cuadro en ~2.8 ms (permitiendo > 120 FPS teóricos en un solo hilo de CPU sin GPU).
* **Consumo de Memoria**: Buffer circular de cuadros RGB de tamaño fijo (< 15 MB).

---

## 5. Implementación y CLI
El protocolo está completamente implementado en:
* Motor central: ``core/pipeline_verifier.py``
* CLI de diagnóstico: ``scripts/e2e_pipeline_tester.py``
* Suite de pruebas automatizadas: ``tests/test_e2e_complete_pipeline.py``
