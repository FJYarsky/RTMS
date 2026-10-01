# ADR-0009: Blindaje de Subprocesos con Windows Job Objects y Supresión de Procesos Huérfanos

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Core / Sistema Operativo / Concurrencia / Resiliencia
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS orquesta múltiples subprocesos externos de alta intensidad computacional para la captura, codificación y distribución de medios (`ffmpeg.exe`, `mediamtx.exe` y reproductores `ffplay.exe`). En entornos de producción sobre Windows, si el proceso principal de Python finaliza de forma anormal (fallo por excepción no controlada, cierre forzado desde el Administrador de Tareas, fallo de segmentación en runtime de CPython o crash de la máquina virtual), los subprocesos hijos no vinculados al kernel continúan ejecutándose indefinidamente en segundo plano.

Estos procesos "huérfanos" (zombies) provocan tres fallos críticos en el sistema:
1. **Bloqueo exclusivo de hardware DirectShow**: Windows mantiene bloqueado el descriptor de la cámara web USB o capturadora HDMI, impidiendo que una nueva instancia de RTMS o aplicaciones de producción como OBS Studio puedan acceder al dispositivo.
2. **Colisión de sockets de red**: Los subprocesos huérfanos retienen los puertos de escucha y publicación (MediaMTX en el puerto 8890, sockets SRT en 9000+, puertos API en 8000), impidiendo el reinicio del servicio (`WSAEADDRINUSE / WinError 10048`).
3. **Fuga silenciosa de recursos de GPU/CPU**: Múltiples instancias huérfanas de FFmpeg codificando señales causan saturación del silicio (NVENC/QSV) y sobrecalentamiento térmico del equipo.

## 2. Factores Decisivos (Decision Drivers)
* **Garantía Ineludible de Limpieza a Nivel Kernel**: La eliminación de subprocesos no debe depender de manejadores en espacio de usuario (`atexit`, `try...finally` o `SIGTERM`), los cuales son eludidos ante un `SIGKILL` o `TerminateProcess`.
* **Cero Huérfanos tras Crash Catastrófico**: El sistema operativo Windows debe garantizar que si el proceso padre desaparece, todos los subprocesos hijos mueran de manera instantánea y simultánea.
* **Compatibilidad con Subprocesos Múltiples**: Debe soportar la asignación dinámica de procesos recién creados sin afectar las cuotas de memoria ni la afinidad de CPU del usuario.
* **Transparencia Operativa**: Debe operar de manera desatendida sin requerir privilegios de administrador (`Administrator/SYSTEM`) en Windows 10 y Windows 11.

## 3. Opciones Consideradas
* **Opción A (Monitoreo por Heartbeat / Watchdog IPC)**: Un proceso supervisor externo que envía pings periódicos y liquida a los hijos si el padre no responde.
  - *Desventajas*: Introduce complejidad arquitectónica adicional, consumo continuo de CPU, riesgo de que el propio supervisor falle o quede huérfano, y latencia de recuperación de varios segundos.
* **Opción B (Manejadores de Señal en Espacio de Usuario `atexit` y `signal`)**: Registrar rutinas de limpieza que iteran sobre las instancias de `subprocess.Popen` invocando `terminate()`.
  - *Desventajas*: Completamente inútil ante excepciones no capturadas a nivel C, congelamiento del intérprete, fallos de alimentación o terminación abrupta mediante el Administrador de Tareas (`taskkill /F`).
* **Opción C (Win32 Job Objects del Kernel de Windows con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`)**: Crear un objeto Job anónimo a través de la API Win32 (`kernel32.dll`) configurado con el flag de límites extendidos `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, asignando cada subproceso (`ffmpeg.exe`, `mediamtx.exe`, `ffplay.exe`) al Job inmediatamente después de su instanciación.

## 4. Decisión
Se adopta la **Opción C**:
1. Se implementa la clase singleton ``JobObjectManager`` en `core/job_object.py`.
2. Al iniciar la aplicación en plataformas Win32, se invoca `kernel32.CreateJobObjectW(None, None)`.
3. Se estructura una llamada a `kernel32.SetInformationJobObject` con la clase de información `JobObjectExtendedLimitInformation` (valor 9), inyectando la estructura `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` con el flag:
   `BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)`
4. En ``core/stream_manager.py``, ``core/mediamtx_mgr.py`` y ``core/preview_mgr.py``, cada vez que se crea un subproceso mediante `asyncio.create_subprocess_exec` o `subprocess.Popen`, se invoca `job_object_manager.assign_process_to_job(proc)`.
5. Se utiliza `kernel32.AssignProcessToJobObject(self.job_handle, handle)` pasando el descriptor del proceso obtenido mediante `kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)`.
6. Al cerrarse el handle del Job (lo cual el kernel de Windows ejecuta incondicionalmente al destruirse el proceso padre, incluso en un Kernel Panic o crash fatal), el planificador de Windows envía una señal de terminación forzada a nivel de kernel a todos los procesos registrados en el Job.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Eliminación Absoluta de Procesos Zombies**: Garantía determinista del 100% de que ningún ejecutable `ffmpeg.exe` ni `mediamtx.exe` sobrevive al cierre o terminación anormal de RTMS.
* **Liberación Inmediata de Hardware**: Los dispositivos de captura DirectShow y cámaras USB quedan disponibles instantáneamente para reconexión o reapertura sin requerir reinicio del sistema ni desconexión física de cables.
* **Inexistencia de Puertos Bloqueados**: Los sockets SRT y MediaMTX se liberan en el kernel, erradicando los errores `WSAEADDRINUSE`.
* **Cero Sobrecarga de CPU**: La vigilancia y recolección es realizada internamente por el subsistema de gestión de objetos del kernel de Windows sin bucles de polling en Python.

### Consecuencias Negativas / Limitaciones (-)
* Funcionalidad restringida a sistemas operativos Windows (`sys.platform == "win32"`). En entornos POSIX (pruebas locales en Linux/macOS), el gestor opera en modo no-op transparente.
* Si el proceso padre se ejecuta dentro de un Job Object heredado sin permisos de anidamiento (`nested jobs` en versiones antiguas de Windows previas a Windows 8), `AssignProcessToJobObject` puede retornar error `ERROR_ACCESS_DENIED`, en cuyo caso el módulo registra un warning y recurre a la limpieza en espacio de usuario sin provocar caídas.

## 6. Validación y Cumplimiento
* Certificado en pruebas unitarias y de estrés en ``tests/test_audit_new_features.py`` y ``tests/test_audit_lifecycle.py``.
* Verificación manual de resiliencia: Ejecutar 4 transmisiones concurrentes, finalizar `python.exe` / `rtms.exe` violentamente desde `cmd` con `taskkill /F /IM rtms.exe`, y verificar con `Get-Process ffmpeg, mediamtx` que todos los subprocesos fueron recolectados instantáneamente por el kernel.
