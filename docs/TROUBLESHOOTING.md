# Guía de Resolución de Problemas (Troubleshooting) — RTMS

Esta guía ofrece soluciones prácticas e instrucciones paso a paso para los incidentes más frecuentes en transmisiones multicámara con RTMS.

---

## 1. OBS Studio / vMix no se conecta al flujo SRT

### Síntoma
En OBS la fuente multimedia o SRT permanece en negro o muestra `Connection refused`.

### Diagnóstico y Solución
1. **Verificar el modo del socket**:
   - En RTMS, el servidor corre en modo **Listener** (`mode=listener`).
   - En OBS Studio o VLC, el receptor debe configurarse en modo **Caller** (`mode=caller`).
   - Ejemplo de URL para OBS:
     ```text
     srt://192.168.1.50:9000?mode=caller&latency=120000
     ```
2. **Contraseña SRT (Passphrase)**:
   - Si la cámara tiene una contraseña configurada en RTMS, debe incluirse en la URL de OBS:
     ```text
     srt://192.168.1.50:9000?mode=caller&latency=120000&passphrase=TU_CLAVE
     ```
3. **Firewall de Windows**:
   - Asegúrate de que los puertos UDP (9000-9200) estén permitidos en la red privada. Ve a la sección **Gestión de Energía / Firewall** en RTMS y presiona **Aplicar Optimizaciones**.

---

## 2. La cámara web no aparece en la lista de dispositivos

### Síntoma
La interfaz muestra "0 cámaras detectadas" o el dispositivo físico no figura en el panel.

### Diagnóstico y Solución
1. **Cámara en uso por otra aplicación**:
   - En Windows, los controladores DirectShow estándar solo permiten que una aplicación acceda a la cámara al mismo tiempo. Cierra Teams, Zoom, Discord u OBS antes de escanear.
2. **Forzar escaneo de hardware**:
   - En la interfaz de RTMS, presiona el botón **Escanear Hardware** para consultar la enumeración DirectShow de Windows.
3. **Permisos de privacidad de cámara en Windows**:
   - Ve a **Configuración de Windows** $\rightarrow$ **Privacidad y seguridad** $\rightarrow$ **Cámara**.
   - Asegúrate de que la opción *"Permitir que las aplicaciones de escritorio accedan a la cámara"* esté **Activada**.

---

## 3. Fallo de Codificador GPU y Fallback a CPU

### Síntoma
En los logs figura el error `error while opening encoder` o `h264_nvenc: Driver does not support the required nvenc API version`.

### Diagnóstico y Solución
- RTMS detecta el error de inicialización de la GPU y conmuta de forma automática a `libx264` (CPU).
- Para recuperar la aceleración por hardware:
  1. Actualiza los controladores oficiales de NVIDIA (GeForce Experience), AMD Adrenalin o Intel Graphics.
  2. Verifica que no haya múltiples instancias de juegos o renderizado 3D saturando la memoria VRAM de la tarjeta.

---

## 4. Recuperación tras Desconexión Física de Cable USB

### Comportamiento Automático
- Si una cámara se desconecta durante una transmisión en vivo, RTMS marca el flujo como **DISCONNECTED** y suspende los reintentos inútiles.
- Al volver a conectar el cable USB, el sincronizador de hardware detecta la reaparición del dispositivo y, si tiene habilitado el autoarranque, relanza el flujo automáticamente.

---

## 5. Elevado Consumo de GPU o Temperatura en Portátiles (e.g. RTX 4050)

### Síntoma
La GPU dedicada (NVIDIA GeForce RTX 4050 Laptop / 3060 / 4060) exhibe frecuencias elevadas, consumo eléctrico constante (~35W-50W) o aumento de temperatura en reposo.

### Diagnóstico y Solución
1. **Cámara Virtual NVIDIA Broadcast en Autoarranque**:
   - Cuando una cámara virtual de IA (`Camera (NVIDIA Broadcast)`) está transmitiendo continuamente, el software de NVIDIA mantiene activos sus modelos de redes neuronales en los Tensor Cores y en el motor 3D, impidiendo que la GPU descienda a estados de ultra bajo consumo (*P-States P8 / D3cold*).
   - **Solución en RTMS v2.1.0**: RTMS detecta automáticamente `NVIDIA Broadcast` como dispositivo virtual y establece `auto_start: false`. Inicia esta cámara únicamente cuando sea estrictamente necesario.
2. **P-States de NVENC**:
   - Al emitir con codificación por hardware (`h264_nvenc`), los controladores NVIDIA fijan la GPU en estado de rendimiento P0/P2 para garantizar la estabilidad de cuadros sin microcortes. En una laptop conectada a la corriente esto es normal y esperado. Si necesitas operar exclusivamente a batería, configura el codificador en `libx264` (CPU) desde los ajustes de la cámara.
