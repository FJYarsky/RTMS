## RTMS v2.2.4 — Ventana Nativa WebView2, System Tray Avanzado y Limpieza Total de Procesos

### 🖥️ Interfaz de Escritorio Nativa y Empaquetado Portable (WebView2)
- **Corrección Crítica de Ventana Nativa en Release Portable**:
  - En la distribución portable generada por PyInstaller, se empaquetan las dependencias nativas de `pythonnet` (`--hidden-import=pythonnet`, `--collect-all=pythonnet`) y se copian automáticamente todas las DLLs de WebView2 (`Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll` y la carpeta de arquitecturas `runtimes/`) junto a `icon.ico` hacia la raíz y `_internal` de `dist/rtms/`.
  - Se elimina definitivamente el fallo silencioso que forzaba a la aplicación a abrirse en el navegador por defecto (Google Chrome) en lugar del entorno de escritorio nativo con aceleración Edge WebView2.
- **Eliminación de Ventanas Duplicadas y Pestañas Periódicas**:
  - `show_window_from_tray()` en `main.py` valida la existencia de la ventana nativa (`_main_window`) e invoca exclusivamente `show()` y `restore()`. Se eliminó cualquier invocación accidental a `webbrowser.open()` cuando el motor nativo está activo.
  - Sincronización robustecida en `acquire_single_instance_lock()` para que segundas instancias pasen el foco a la ventana existente mediante señalización IPC en lugar de desplegar interfaces concurrentes.

### ⚡ Gestión Avanzada del Ciclo de Vida y Limpieza de Procesos
- **Terminación Total de Procesos (In-App y System Tray)**:
  - Nuevo módulo `core/process_cleanup.py` que implementa `terminate_all_processes(force=True)`.
  - Detiene ordenadamente hilos de captura, transmisiones activas y previsualizaciones, y elimina árboles de procesos huérfanos de FFmpeg y FFplay (`taskkill /F /T` y `psutil`).
  - Libera el mutex de instancia única (`single_instance_lock`), finaliza el System Tray y llama a `os._exit(0)`.
  - Botón `⚡ Salir / Finalizar` en la barra superior y en la pestaña de Sistema con diálogo modal de confirmación.
  - Opción de menú contextual `Finalizar todos los procesos` en la bandeja del sistema.
  - Nuevo endpoint protegido `POST /api/system/shutdown`.
- **Restablecimiento a Valores de Fábrica ("Factory Reset")**:
  - Nuevo endpoint protegido `POST /api/system/factory_reset` que requiere confirmación explícita (`confirm: true`).
  - Elimina de forma segura la configuración (`rtms_config.json*`), copias de respaldo, archivos de registro (`rtms.log*`) y directorios de almacenamiento en `%LOCALAPPDATA%\RTMS\`.
  - Ejecuta la terminación total de procesos para garantizar que el siguiente arranque sea 100% limpio como una primera instalación.
  - Botón `🗑️ Restablecer a Valores de Fábrica` en la sección de Sistema con modal de confirmación y advertencia.
- **Renombramiento de "Parada de Emergencia" a "Detención Global"**:
  - Sustituida la nomenclatura alarmista por `⏹️ Detener Todo` / `Detención Global` en la interfaz, adaptando el color del botón a tono ámbar sobrio.

### 🎛️ Integración y Rediseño del System Tray
- **Icono Vectorial Moderno**: Rediseñado el icono por defecto en `core/tray_icon.py` con diseño de esquinas redondeadas en color grafito oscuro (`#1E293B`), lente concéntrico cian (`#06B6D4` / `#0891B2`) y punto indicador de captura.
- **Menú Contextual Enriquecido**: Agregadas las acciones `Detener todas las transmisiones`, `Finalizar todos los procesos` y tooltip dinámico con versión del sistema (`RTMS v2.2.4 — Real-Time Multicam System`).
- **Restauración Fiable**: El botón `Mostrar RTMS` enfoca de forma consistente la ventana nativa de la aplicación sin abrir navegadores externos.

### 📊 Monitoreo de Plataforma Windows y Auditoría Integral
- **Detalles Completos de Entorno Windows**:
  - Detección de edición de Windows, Build Number, UBR (Update Build Revision) y arquitectura (64-bit / ARM64) mediante consulta directa al Registro de Windows (`SOFTWARE\Microsoft\Windows NT\CurrentVersion`).
  - Exposición en `/api/system/status`, integración en el HUD superior y tabla de diagnóstico del sistema.
- **Resolución de Auditorías Técnicas (Claude N1-N9 & ChatGPT P0-P2)**:
  - Persistencia de `ignored_devices` en `core/config_mgr.py` para evitar que el hotplug de DirectShow reactive cámaras eliminadas.
  - Corrección de `SecretFilter` para soportar argumentos `%s` sin generar excepciones `TypeError`.
  - Tickets efímeros de preview de uso único (single-use) e invalidación por dispositivo con límite de capacidad estricto (cap a 100).
  - Documentación detallada en `docs/TROUBLESHOOTING.md` sobre contención de sockets en modo SRT Listener.
  - Incorporación de `CODE_OF_CONDUCT.md` bajo el estándar Contributor Covenant v2.1.
  - Eliminación absoluta de datos personales de contacto no profesionales en el 100% de los archivos.
  - Estandarización permanente de encabezados y descripciones funcionales en todos los módulos.
  - 93 pruebas unitarias y de integración pasando al 100% y 0 errores de linter.
 
