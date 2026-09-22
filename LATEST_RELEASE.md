# RTMS v2.5.0 — Core Media Server, Pipeline Desacoplado, Blindaje de Kernel y Persistencia ACID

**Fecha:** 22 de Septiembre de 2026 | **Versión:** `v2.5.0`

---

### 🌐 Ingesta Desacoplada con MediaMTX (Opción A Estándar Broadcast)
- **Media Server Local (`bin/mediamtx.exe` v1.9.3)**:
  - FFmpeg publica localmente de forma ininterrumpida como caller (`srt://127.0.0.1:8890?streamid=publish:{cam_id}&mode=caller`).
  - MediaMTX expone el servicio en la red LAN a través de un puerto central SRT (por defecto `8890`, configurable en Ajustes en los rangos recomendados `8890-8990` o `9000-9200`).
  - Formato universal de conexión para OBS Studio y vMix:
    `srt://{ip}:{mediamtx_port}?streamid=read:{cam_id}&latency={latency}`.
  - **Inmunidad Total ante Desconexiones de Clientes**: Las aperturas, cierres o reconexiones de OBS Studio jamás detienen a FFmpeg ni causan reinicios de hardware ni parpadeos en las cámaras físicas.
  - Múltiples receptores pueden conectarse a la misma cámara simultáneamente sin sobrecargar la CPU del emisor.

---

### 🛡️ Blindaje de Procesos por Kernel (Win32 Job Objects)
- **Cero Procesos Huérfanos (`core/job_object.py`)**:
  - Implementación nativa con `kernel32.dll` del flag `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (0x2000).
  - Todas las instancias de FFmpeg, MediaMTX y visores FFplay quedan asociadas al Job Object de Windows.
  - Si RTMS es cerrado o finalizado desde el Administrador de Tareas, el kernel de Windows liquida atómica e instantáneamente todos los procesos secundarios.
- **Registro Centralizado de Tareas (`core/task_registry.py`)**:
  - Supervisión, drenaje y cancelación limpia de corrutinas asíncronas en el shutdown.

---

### 💾 Persistencia Transaccional ACID (SQLite WAL)
- **Capa de Repositorio (`core/repository/`)**:
  - Reemplazo de JSON monolítico por base de datos SQLite en modo `WAL` (`Write-Ahead Logging`) con `busy_timeout=5000` y transacciones inmediatas.
  - **Migración Automática Reversible**: Detección transparente de `config.json`, migración atómica a `config/rtms.db`, creación de copia de seguridad inmutable `config.json.v2.4.1.bak` y réplica exportada sincronizada.

---

### 🔄 Papelera y Recuperación de Cámaras Eliminadas (Bugfix Hallazgo #20)
- **Sección de Dispositivos Ocultados / Eliminados**:
  - Nuevos endpoints API: `GET /api/devices/ignored`, `POST /api/devices/unignore`, `POST /api/devices/unignore_all`.
  - Nueva sección colapsable en la interfaz Web con contador badge y botón interactivo `🔄 Restaurar Cámara` individual y masivo, devolviendo las cámaras a estado `STOPPED` con reasignación dinámica de puertos ante colisiones.

---

### 🧪 Calidad, CI/CD y Gobernanza GitHub
- Suite completa de 139 pruebas automatizadas (100% aprobadas).
- Tipado estricto `mypy` verificado en `core/` y `api/`.
- Linters y formato `ruff` validados sin advertencias.
- Catálogo canónico de GitHub preservado en 31/31 elementos raíz (`scripts/manage_descriptions.py --check`).
- Empaquetado portable con PyInstaller actualizado (`build_portable.bat`) con inclusión de `mediamtx.exe`, `mediamtx.example.yml` y soporte de `aiosqlite`.
- Avisos de licencias de terceros actualizados con la licencia MIT de MediaMTX (`THIRD_PARTY_NOTICES.md`).
