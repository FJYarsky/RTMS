# RTMS v2.3.0 — Seguridad Crítica, Gobernador Energético Win32 y Estandarización de Arquitectura

**Fecha:** 19 de Septiembre de 2026 | **Versión:** `v2.3.0`

---

### 🛡️ Seguridad Crítica y Protección de Sesión (Hotfixes P0)
- **Corrección de Limpieza Asíncrona de Procesos (`core/process_cleanup.py`)**:
  - Resuelto fallo P0-01 encapsulando `asyncio.gather` dentro de una corrutina real antes de llamar a `asyncio.run_coroutine_threadsafe()`, garantizando la terminación ordenada de los managers de streaming y preview sin excepciones de runtime.
- **Filtro Estricto y Seguro de Terminación de Procesos (`core/process_cleanup.py`)**:
  - Resuelto fallo P0-02 acotando la terminación forzada exclusivamente a subprocesos hijos de RTMS (`ppid == my_pid`), binarios ubicados en el directorio `bin/` de RTMS o líneas de comando con marca `rtms`. Protege instancias externas de FFmpeg utilizadas por otras aplicaciones en el sistema del usuario.
- **Eliminación de Fuga de Tokens en Query Parameters (`api/routes.py`)**:
  - Resuelto fallo P0-03 eliminando la aceptación de tokens en la URL (`?token=...`), retornando código HTTP 403. Incorporadas cabeceras `Cache-Control: no-store, no-cache, must-revalidate` y `Pragma: no-cache` en `/api/stream/{device}/connect_url`.
- **Autenticación por Cookie HttpOnly y Eliminación de Meta Tag (`main.py` y `gui/templates/index.html`)**:
  - Resuelto fallo P0-04 eliminando `<meta name="rtms-token">` del DOM y del contexto de plantilla. Emisión de cookie segura `rtms_session` con flags `httponly=True, samesite='lax'` y configuración de `credentials: 'same-origin'` en todas las peticiones `apiFetch` de la interfaz web.
- **Corrección de Visualización y Revelado de Contraseña en URLs (`gui/static/app.js`)**:
  - Las URLs de conexión mostradas en las tarjetas cargan inmediatamente la contraseña descifrada para streams activos e incorporan un botón conmutable para ocultar/mostrar la clave (icono 👁️ / 🔒), garantizando la copia exacta al portapapeles.

---

### ⚡ Gestión Energética Profesional y Nativa (Win32)
- **Nuevo Módulo de Energía Nativo (`core/power_mgr.py`)**:
  - Implementación de control energético mediante APIs Win32 nativas (`powrprof.dll`, `kernel32.dll`) sin invocar scripts externos de PowerShell, eliminando alertas de antivirus y falsos positivos.
- **Gobernador Dinámico de Energía (`DynamicPowerGovernor`)**:
  - Elevación automática al plan de energía de **Alto Rendimiento** de Windows en cuanto inicia al menos una transmisión activa (`active_streams >= 1`) y restauración inmediata y transparente del plan original al concluir todas las transmisiones (`active_streams == 0`).
- **Prevención Nativa de Suspensión de Pantalla y Equipo**:
  - Activación continua de `SetThreadExecutionState` (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED`) durante la operación activa.
- **Optimización de Adaptadores de Red Vía Registro**:
  - Desactivación de ahorro de energía (`PnPCapabilities = 24`) mediante manipulación directa en el registro con `winreg` y verificación de privilegios `is_admin()`.
- **Rollback Atómico y Persistencia**:
  - Creación de respaldo seguro en `config/power_backup.json` con restauración garantizada de directivas originales al cerrar o solicitar la restauración.

---

### 🔄 Ruptura Limpia de Retrocompatibilidad (< 2.3.0)
- **Esquema de Configuración v4 (`core/config_mgr.py`)**:
  - Actualizado a `CURRENT_SCHEMA_VERSION = 4` y purgadas todas las rutinas de migración heredadas v1 y v2.
  - Detección automática de versiones de configuración previas (< 4) con respaldo seguro en `config/config.json.legacy_v2_bak` y reinicialización limpia a valores por defecto para v2.3.0.
  - Eliminado el script obsoleto `run_silent.vbs` y actualizadas las referencias de arranque en el proyecto.

---

### 🛠️ Estandarización de Arquitectura y Herramientas (PEP 621)
- **Modernización de pyproject.toml**:
  - Configuración del sistema de empaquetado estándar `hatchling` con metadatos PEP 621.
  - Incorporadas reglas de linting y formato estrictas con Ruff (`line-length = 120`, reglas `E`, `F`, `W`, `I`, `B`), tipado con Mypy y configuración de Pytest.
  - 100% de la base de código formateada y alineada con estándares modernos de Python.
