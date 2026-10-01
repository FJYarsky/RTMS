# RFC-0005: Gobernanza de Blindaje de Procesos a Nivel de Kernel (Win32 Job Objects) y Ciclo de Vida Resiliente

* **Estado**: Implementado
* **Fecha de Creación**: 2026-10-01
* **Última Actualización**: 2026-10-01
* **Autor(es)**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área / Componente**: Core / Kernel Win32 / Concurrencia / Procesos / Resiliencia

---

## 1. Resumen Ejecutivo (Abstract)
Este documento especifica la arquitectura del sistema de blindaje de procesos secundarios y ciclo de vida resiliente de RTMS. Establece la utilización de Win32 Job Objects con el límite de kernel `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, el registro centralizado de tareas asíncronas (`TaskRegistry`), la jerarquía de señales de apagado del sistema operativo (Win32 Console Control Handlers y WM_CLOSE) y el protocolo de recolección de puertos de red huérfanos, garantizando que el sistema jamás deje procesos secundarios activos ni recursos de hardware bloqueados ante fallos catastróficos.

---

## 2. Motivación y Casos de Uso
En sistemas de video y streaming en tiempo real ejecutados sobre Windows, la finalización abrupta de la aplicación principal (por fallo de alimentación, cierre forzado desde el Administrador de Tareas, excepción crítica en el runtime de Python o reinicio forzado del sistema) deja habitualmente procesos hijos huérfanos (`ffmpeg.exe`, `mediamtx.exe`, `ffplay.exe`). 

Las consecuencias de estos procesos huérfanos son críticas:
1. **Bloqueo Ineludible del Descriptor DirectShow**: El controlador de la cámara USB permanece bloqueado por el kernel de Windows para el PID huérfano. Ni una nueva instancia de RTMS ni OBS Studio pueden abrir la cámara hasta que el usuario reinicie físicamente la PC o mate el proceso mediante comandos manuales en la consola.
2. **Puertos de Red Retenidos en Estado CLOSE_WAIT**: MediaMTX y los sockets SRT continúan ocupando los puertos 8890 y 9000+, provocando errores `WinError 10048` al reabrir el software.
3. **Fugas de Potencia de GPU**: Codificadores NVENC retenidos por instancias invisibles degradan el rendimiento de otras aplicaciones.

Esta especificación estandariza el mecanismo a nivel de kernel para eliminar el problema de raíz sin depender de manejadores de espacio de usuario.

---

## 3. Especificación Detallada del Diseño (Detailed Design)

### 3.1 Estructuras de Datos del Kernel Win32
Para interactuar con la API del kernel de Windows sin dependencias de extensiones compiladas en C, se definen las estructuras binarias de ctypes exactas correspondientes a `winnt.h`:

```python
class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]
```

### 3.2 Diagrama de Secuencia de Asignación y Recolección por Kernel
```mermaid
sequenceDiagram
    autonumber
    participant KRN as Windows Kernel (ntoskrnl.exe)
    participant RTMS as Proceso Principal RTMS (Python)
    participant JOB as Win32 Job Object
    participant FF as Worker FFmpeg (Subproceso)

    RTMS->>KRN: CreateJobObjectW(NULL, NULL)
    KRN-->>RTMS: Handle hJob
    RTMS->>KRN: SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, flags=0x2000)
    Note over JOB: Flag activo:<br/>JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    RTMS->>KRN: CreateProcess / asyncio.subprocess ("ffmpeg.exe ...")
    KRN-->>RTMS: Subprocess PID
    RTMS->>KRN: OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, PID)
    KRN-->>RTMS: Handle hProcess
    RTMS->>JOB: AssignProcessToJobObject(hJob, hProcess)
    RTMS->>KRN: CloseHandle(hProcess)

    alt Caso Normal: Cierre Ordenado
        RTMS->>FF: SIGTERM / stop_stream()
        FF-->>RTMS: Exit 0
    else Caso Catastrófico: Crash de RTMS / TerminateProcess
        Note over RTMS: Proceso RTMS muere instantáneamente
        KRN->>JOB: Cierre automático de todos los handles de hJob
        KRN->>FF: TerminateProcess(FF, 1) ejecutado directamente por el Kernel
        Note over FF: Subproceso liquidado en &lt;1 ms.<br/>Hardware liberado inmediatamente.
    end
```

### 3.3 Registro Centralizado y Drenaje Ordenado (`TaskRegistry`)
Para tareas asíncronas dentro de Python (`asyncio`), se implementa [`TaskRegistry`](file:///C:/Users/joaqu/Desktop/RTMS/core/task_registry.py):
1. **Registro Inmediato**: Cada corrutina en segundo plano (watchdog, sondeo de hardware, telemetría, ping óptico) se crea mediante `task_registry.create_task(coro, name=...)`.
2. **Auto-recolección**: Se asocia un callback `task.add_done_callback(self._tasks.discard)` para evitar acumulación de referencias de memoria en tareas completadas.
3. **Protocolo de Drenaje en Shutdown**:
   Durante el ciclo de apagado de FastAPI (`lifespan`), se ejecuta `await task_registry.cancel_all(timeout=3.0)`:
   - Se emite `task.cancel()` a todas las tareas pendientes.
   - Se espera con `asyncio.wait(pending, timeout=3.0)` a que las corrutinas finalicen sus bloques `finally`.
   - Se suprimen las excepciones `asyncio.CancelledError`.

---

## 4. Consideraciones de Rendimiento y Cómputo (Performance & Footprint)
* **Impacto en CPU**: 0% de CPU continuo. Las Win32 APIs de Job Objects no realizan sondeo activo; la gestión es totalmente pasiva e impulsada por el despachador de objetos del kernel de Windows.
* **Tiempo de Asignación**: La llamada a `AssignProcessToJobObject` toma menos de 0.05 milisegundos tras la creación de cada subproceso.

---

## 5. Consideraciones de Seguridad (Security Considerations)
* **Permisos Restringidos**: Se solicitan estrictamente los derechos mínimos necesarios sobre el descriptor del subproceso: `PROCESS_SET_QUOTA | PROCESS_TERMINATE` (0x0100 | 0x0001), evitando requerir `PROCESS_ALL_ACCESS`.
* **Aislamiento de Entorno**: El Job Object es anónimo (sin nombre en el namespace de objetos globales), evitando que procesos maliciosos no autorizados puedan manipular el handle del Job.

---

## 6. Compatibilidad y Migración (Backwards Compatibility)
* Totalmente compatible con Windows 10 (todas las compilaciones) y Windows 11.
* En sistemas POSIX o emuladores Wine, la clase detecta `sys.platform != "win32"` y desactiva las llamadas de kernel sin arrojar excepciones.

---

## 7. Plan de Verificación e Implementación
* **Pruebas de Asignación y Blindaje**: [`tests/test_audit_new_features.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_new_features.py).
* **Pruebas de Ciclo de Vida y Drenaje**: [`tests/test_audit_lifecycle.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_lifecycle.py).
* **Pruebas de Concurrencia Extrema**: [`tests/test_stress_concurrency.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_stress_concurrency.py).
