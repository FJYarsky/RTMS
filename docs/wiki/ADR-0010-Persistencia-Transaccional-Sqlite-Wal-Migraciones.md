# ADR-0010: Persistencia Transaccional ACID en SQLite WAL y Migraciones Idempotentes

* **Fecha**: 2026-10-01
* **Estado**: Aceptado (Supera y formaliza el almacenamiento plano JSON)
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Core / Persistencia / Base de Datos / Concurrencia
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
En las versiones tempranas de RTMS, el estado del sistema, las preferencias de captura y el inventario de cámaras se almacenaban en un único archivo de texto plano `config/config.json`. Conforme el sistema incorporó persistencia reactiva, autoarranque desatendido, sondeos concurrentes y peticiones REST simultáneas desde la GUI y la API FastAPI, el modelo de archivo plano presentó limitaciones severas:

1. **Condiciones de Carrera (Race Conditions) y Sobrescritura Concurrente**: Cuando múltiples peticiones de actualización concurrían (ej. asignación automática de puertos mientras la GUI guardaba la resolución de una cámara), se producían lecturas y escrituras no atómicas que truncaban o corrompían el archivo JSON.
2. **Vulnerabilidad ante Fallos Eléctricos o Cierres Abruptos**: Una interrupción de energía durante una llamada a `json.dump()` dejaba el archivo con tamaño de 0 bytes o sintaxis truncada, impidiendo arranques posteriores de la aplicación.
3. **Ausencia de Modelo de Migraciones Formal**: La adición de nuevos campos de configuración (ej. `srt_passphrase`, `udp_mode`, `is_virtual`, `zerolatency`) requería parches heurísticos ad-hoc con valores por defecto dispersos en el código fuente.

## 2. Factores Decisivos (Decision Drivers)
* **Garantías Transaccionales ACID**: Soporte inquebrantable de Atomicidad, Consistencia, Aislamiento y Durabilidad.
* **Concurrencia Lectura/Escritura No Bloqueante**: Múltiples hilos (FastAPI, System Tray, tareas de sondeo de hardware DirectShow) deben poder consultar la configuración simultáneamente sin bloquear las escrituras de cambios de estado.
* **Portabilidad y Zero-Config**: El motor de persistencia debe estar embebido en el binario sin requerir instalación de servidores externos (como PostgreSQL, MySQL o Redis).
* **Migraciones Idempotentes y Reversibles**: Capacidad de evolucionar el esquema de base de datos entre versiones de software sin pérdida de datos del usuario y con respaldo previo inmutable del esquema heredado.

## 3. Opciones Consideradas
* **Opción A (Bloqueo de Archivo `filelock` sobre `config.json`)**: Mantener el formato JSON y añadir exclusión mutua basada en archivos.
  - *Desventajas*: No resuelve la vulnerabilidad de corrupción ante cortes abruptos de energía; serializa todas las lecturas degradando la latencia de la API; no provee soporte para consultas relacionales ni control formal de esquema.
* **Opción B (Base de Datos Clave-Valor Embebida tipo RocksDB / LMDB)**: Alto rendimiento para pares clave-valor.
  - *Desventajas*: Dependencias de compiladores de C++ complejas para empaquetado portable con PyInstaller en Windows; ausencia de lenguaje declarativo de consultas y tipado estricto.
* **Opción C (Motor Embebido SQLite en Modo Write-Ahead Logging - WAL)**: Utilizar el motor relacional SQLite nativo de la biblioteca estándar de Python, configurado con `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA busy_timeout = 5000` y el patrón Repositorio (`ConfigRepository`).

## 4. Decisión
Se adopta la **Opción C**:
1. Se crea el subsistema de base de datos en ``core/repository/database.py`` con esquema relacional normalizado:
   - `cameras`: Tabla para metadatos de hardware, resolución, fps, bitrate, protocolo, passphrase y puertos.
   - `system_settings`: Almacén de pares clave-valor para variables globales del entorno.
   - `schema_migrations`: Registro inmutable de versiones de migración aplicadas con marca de tiempo.
   - `ignored_devices`: Lista negra de dispositivos de video excluidos del inventario.
2. Se configuran de manera innegociable los siguientes pragmas de rendimiento y estabilidad en cada conexión:
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA busy_timeout = 5000;
   PRAGMA foreign_keys = ON;
   ```
3. El modo **Write-Ahead Logging (WAL)** desacopla completamente los lectores de los escritores: las consultas de lectura de la API o la GUI acceden a la base de datos sin bloquear ni ser bloqueadas por transacciones de escritura activas.
4. Se implementa ``core/repository/migrator.py`` para la migración atómica y transparente del archivo heredado `config/config.json` hacia `config/rtms.db`, creando automáticamente una copia de respaldo inmutable (`config.json.v2.4.1.bak`) antes de la transacción.
5. Se expone una capa de acceso desacoplada ``ConfigRepository`` con métodos concurrentes seguros (`get_camera`, `upsert_camera`, `delete_camera`, `get_all_cameras_sync`).

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Inmunidad ante Corrupción por Crash**: La durabilidad de WAL asegura que una caída súbita del sistema mantenga la consistencia transaccional del archivo `rtms.db`, recuperando el último estado confirmado al reiniciar.
* **Escalabilidad de Lecturas**: Múltiples componentes concurrentes leen la configuración en submilisegundos sin riesgo de contención de locks.
* **Evolución Controlada del Esquema**: El versionado mediante `schema_migrations` permite que actualizaciones futuras apliquen sentencias `ALTER TABLE` incrementales y seguras.
* **Migración Automática Silenciosa**: Los usuarios que actualizan desde versiones con `config.json` no sufren pérdida de sus configuraciones previas ni requieren pasos manuales.

### Consecuencias Negativas / Limitaciones (-)
* En entornos de red compartida (directorios SMB / NFS), el modo SQLite WAL no es seguro debido a problemas de coherencia en el bloqueo de memoria compartida POSIX/SMB. Se documenta formalmente que `rtms.db` debe residir siempre en el almacenamiento local de la máquina.

## 6. Validación y Cumplimiento
* Pruebas de persistencia transaccional y atomicidad en ``tests/test_config_persistence.py``.
* Cobertura de migración y aislamiento de base de datos en ``tests/test_config_isolation.py`` y ``tests/test_audit_v260_features.py``.
