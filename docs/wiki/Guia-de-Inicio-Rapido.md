# Guía de Inicio Rápido (Quickstart) — RTMS

Esta guía proporciona las instrucciones operativas para desplegar y configurar RTMS en un entorno de producción en vivo en menos de 5 minutos.

---

## 1. Requisitos Previos del Sistema

* **Sistema Operativo**: Microsoft Windows 10 (Build 19041+) o Windows 11 de 64 bits.
* **Procesador**: Intel Core i5/i7 (8va Gen+) o AMD Ryzen 5/7 (Serie 3000+).
* **Memoria RAM**: 8 GB mínimo (16 GB recomendado para 4 o más cámaras simultáneas).
* **Aceleración por Hardware (Opcional pero recomendado)**:
  - NVIDIA GeForce / Quadro con soporte NVENC.
  - Intel Core con Gráficos Integrados UHD/Iris Xe (Intel Quick Sync Video - QSV).
  - AMD Radeon con soporte AMF.
* **Componentes de Software**:
  - Microsoft Edge WebView2 Runtime (preinstalado en Windows 10/11 actualizado).
  - FFmpeg 7.x/8.x (incluido automáticamente en la versión portable de RTMS).

---

## 2. Instalación y Lanzamiento

### Opción A: Distribución Portable de Producción (Recomendado para Operadores)
1. Descarga el paquete comprimido más reciente desde la sección de [Releases de GitHub](https://github.com/FJYarsky/RTMS/releases) (`RTMS-v2.x.x-portable.zip`).
2. Descomprime el archivo en un directorio local de alta velocidad (ej. `C:\RTMS\`).
   > [!IMPORTANT]
   > No ejecutes RTMS desde unidades compartidas de red (SMB/NFS) para garantizar la durabilidad transaccional de SQLite WAL.
3. Ejecuta `rtms.exe` (o `run.bat`).
4. Se abrirá la ventana de escritorio con el Dashboard reactivo y aparecerá el icono de RTMS en la Bandeja del Sistema (System Tray).

### Opción B: Entorno de Desarrollo (Python)
```bash
# Clonar el repositorio
git clone https://github.com/FJYarsky/RTMS.git
cd RTMS

# Instalar dependencias con uv o pip
uv pip install -e .

# Iniciar la aplicación
python main.py
```

---

## 3. Configuración y Arranque del Primer Stream

### Paso 1: Detección de Dispositivos DirectShow
1. En el panel superior, haz clic en **Escanear Cámaras** (o el sistema las detectará automáticamente al inicio).
2. RTMS consultará el bus DirectShow y mostrará las tarjetas capturadoras y cámaras web USB disponibles.

### Paso 2: Configuración de la Señal de Video
1. Selecciona la cámara deseada.
2. Define los parámetros de captura:
   - **Resolución**: 1280x720 (720p) o 1920x1080 (1080p).
   - **Tasa de Cuadros**: 30 FPS o 60 FPS.
   - **Bitrate Objetivo**: 2500 kbps (720p) o 4500 kbps (1080p).
   - **Protocolo de Salida**: `SRT` (recomendado para producción con pérdida cero de paquetes) o `UDP Multicast` (para redes locales cerradas).
   - **Passphrase**: Opcional; si se define, la transmisión se cifra con AES-128 simétrico.

### Paso 3: Inicio de Transmisión
1. Presiona el botón **Iniciar Transmisión** (`▶ Iniciar`).
2. El indicador de estado transicionará de `STARTING` a `RUNNING` en menos de 1.5 segundos.
3. El HUD mostrará métricas en tiempo real a 10 Hz: FPS reales, Bitrate emitido y paquetes descartados.

---

## 4. Conexión de Clientes Receptores (OBS Studio / vMix / VLC)

### Recepción en OBS Studio vía SRT
1. En OBS Studio, añade una fuente de tipo **Fuente multimedia** (*Media Source*).
2. Desmarca la casilla *"Archivo local"*.
3. En el campo **Entrada** (*Input*), ingresa la URL SRT generada por RTMS:
   ```text
   srt://127.0.0.1:8890?streamid=read:cam_1&latency=50000
   ```
   *(Si configuraste contraseña, agrega `&passphrase=TU_CLAVE`)*.
4. En **Almacenamiento en búfer de red**, configura `0 ms` o `50 ms`.
5. Haz clic en Aceptar. La señal aparecerá en tiempo real con una latencia inferior a 100 ms.

### Recepción en VLC Player vía UDP
Si seleccionaste emisión UDP Multicast:
```bash
vlc.exe "udp://@239.255.0.1:9000" :network-caching=50 :clock-jitter=0
```

---

## 5. Control desde la Bandeja del Sistema (System Tray)

Cuando minimizas la ventana principal de RTMS, la aplicación permanece ejecutándose en segundo plano para no interrumpir las transmisiones en vivo:
* **Clic Izquierdo en el Icono**: Restaura o trae al frente la ventana principal.
* **Clic Derecho en el Icono**: Despliega el menú contextual con opciones rápidas:
  - *Mostrar Panel de Control*
  - *Detener Todas las Transmisiones*
  - *Salir de RTMS* (ejecuta el drenaje ordenado y apagado seguro).

Para más detalles operativos avanzados, consulta el [[Runbook de Operaciones|Runbook-y-Operaciones]].
