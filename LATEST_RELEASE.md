# RTMS v2.5.1 — Compatibilidad de Reproducción SRT (VLC), Parches de Seguridad CodeQL y Sincronización en Memoria

**Fecha:** 22 de Septiembre de 2026 | **Versión:** `v2.5.1`

---

### 🎬 Compatibilidad Total de Reproducción SRT (VLC Media Player, ffplay, OBS)
- **Sintaxis Canónica RFC 3986**:
  - Inclusión de barra delimitadora (`/`) antes de los parámetros query en las URLs SRT generadas (`srt://IP:PORT/?streamid=read:{cam_id}`).
  - Resuelve la incompatibilidad en VLC 3.0 donde el parser de red descartaba el `streamid` al omitir la barra de ruta, impidiendo la reproducción.
- **Normalización de Latencia y Prevención de Retardo**:
  - Eliminado el parámetro `latency` de la URL cliente entregada por la API y GUI.
  - Corrige el problema de congelamiento/buffering de 2 minutos (120 s) provocado por la discrepancia de unidades (microsegundos en FFmpeg vs milisegundos en el módulo `access_srt` de VLC).
  - La latencia se negocia de forma óptima a nivel de servidor (120 ms por defecto).
- **Contraseña SRT Limpia por Defecto**:
  - Las cámaras recién añadidas o detectadas se configuran sin contraseña (`srt_passphrase: ""`), permitiendo la reproducción inmediata en clientes SRT estándar sin autenticación (`ERROR:BADSECRET`).
  - La protección criptográfica por contraseña se mantiene disponible de forma opcional mediante el modal de ajustes de cada cámara.

---

### 🛡️ Parches de Seguridad CodeQL (Alertas #11 y #12)
- **Alerta #11 (CWE-116 - Incomplete string escaping or encoding)**:
  - Corregido en `gui/static/app.js`: se reemplazó la concatenación insegura de JavaScript en atributos `onclick` por enlace declarativo `data-device-path="${escapeHtml(dev.device_path)}"` consumido de manera segura mediante `this.dataset.devicePath`.
- **Alerta #12 (CWE-312 - Clear-text storage of sensitive information)**:
  - Corregido en `core/mediamtx_mgr.py`: se eliminó el almacenamiento en texto claro de contraseñas SRT en el archivo `config/mediamtx.yml` en disco.
  - La configuración de rutas protegidas y contraseñas de lectura (`srtReadPassphrase`) se gestiona ahora exclusivamente en memoria a través de la API REST local de MediaMTX (`/v3/config/paths/add` y `/v3/config/paths/patch`).

---

### ⚡ Sincronización Dinámica de Rutas en MediaMTX
- Nuevos métodos asíncronos `sync_paths_api()` y `sync_path_api()` para actualización en caliente de credenciales y rutas en el Media Server.
- Sincronización automática invocada al iniciar MediaMTX, al actualizar o eliminar configuraciones de cámaras en la API REST y durante el ciclo de sincronización con hardware.

---

### 🧪 Calidad, Verificación y Suite de Pruebas
- Suite completa de 145 pruebas automatizadas (140 aprobadas, 5 omitidas de hardware físico).
- Linters y formateador `ruff` validados sin advertencias.
- Catálogo canónico de GitHub preservado en 31/31 elementos raíz (`scripts/manage_descriptions.py --check`).
