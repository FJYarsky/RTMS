# RTMS v2.4.1 — Corrección de Detección de Dispositivos, Desconexión Hotplug y Control de Inicio

**Fecha:** 22 de Septiembre de 2026 | **Versión:** `v2.4.1`

---

### 🎥 Corrección Forense de Detección DirectShow (Micrófonos vs Video)
- **Aislamiento Estricto de Cámaras de Video (`core/hardware.py`)**:
  - Detección precisa de salida moderna de FFmpeg 7.x+ mediante marcadores `(video)`, `(audio)`, `(none)` y corchetes `[in#`.
  - Eliminado por completo el falso positivo al desactivar la webcam de la laptop con la tecla F5 o interruptor físico: en lugar de caer al parser heredado y capturar erróneamente los micrófonos del sistema, el sistema identifica correctamente 0 dispositivos de video y retorna `[]`.
  - Filtro canónico por GUIDs de DirectShow: exclusión automática e incondicional de dispositivos bajo la categoría `KSCATEGORY_AUDIO` (`33D9A762-90C8-11D0-BD43-00A0C911CE86` / `4DF0A701-02CD-11CF-8356-0080C73DF13A`) y rutas DirectShow con prefijo `@device_cm_`.

---

### 🔌 Manejo Reactivo de Desconexión Física (Hotplug)
- **Transición Inmediata a `DISCONNECTED` (`core/stream_manager.py`)**:
  - Al desenchufar una cámara USB o apagarla por hardware, los errores `ErrorCategory.DEVICE` son interceptados al instante. El proceso de FFmpeg se detiene ordenadamente, pasando el stream a `State.DISCONNECTED` sin penalizar contadores de error de software ni entrar en ciclos de reintentos innecesarios con backoff.
  - **Detección de Congelamiento a 0 FPS**: Watchdog optimizado que detecta streams activos sin entrega de cuadros por más de 8 segundos continuos. Si el hardware desapareció de DirectShow, se detiene el proceso y se marca `DISCONNECTED`.
  - **Reconexión Automática Limpia**: Al volver a enchufar la cámara o reactivarla por teclado, el sistema limpia estados de falla anteriores y, si la cámara posee `auto_start = True`, reanuda la transmisión automáticamente en menos de 5 segundos.
  - **Sondeo Acelerado**: Intervalo de sondeo periódico de hardware reducido a 5 segundos (anteriormente 20 segundos).

---

### ⚙️ Control de Inicio y Política de Carga Inicial
- **Desactivación de Transmisión Masiva al Iniciar (`core/config_mgr.py`)**:
  - Las cámaras recién descubiertas en el sistema se registran con `auto_start = False` por defecto. Al iniciar RTMS por primera vez, las cámaras permanecen en reposo (`STOPPED`), permitiendo al usuario decidir individualmente cuáles iniciar o activar para inicio automático.
  - Plantillas de configuración por defecto actualizadas con `unattended_autostart: false`.

---

### 🧹 Limpieza de Ramas y Catálogo GitHub Oficial
- Eliminación de branches y worktrees temporales huérfanos. Rama `main` establecida como única rama activa.
- Catálogo oficial de 31 elementos raíz verificado y sincronizado al 100%.
