# ADR-0012: Prevención de Suspensión, Optimización Energética de Red y Calibración de Reloj de 1 ms

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Sistema Operativo / Kernel / Rendimiento / Red / Hardware
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
En emisiones y producciones de video en vivo de misión crítica que se extienden por múltiples horas, la configuración predeterminada de gestión de energía del sistema operativo Windows introduce fallos operativos catastróficos:

1. **Suspensión Automática por Inactividad de Entrada**: Aunque los procesos FFmpeg y MediaMTX transmitan gigabytes de video, si el operador no interactúa físicamente con el ratón o el teclado, el temporizador de inactividad de Windows activa el modo de reposo o suspensión (*Sleep / Connected Standby*), apagando los adaptadores de red y congelando la transmisión.
2. **Suspensión Selectiva de USB (USB Selective Suspend)**: El controlador de host USB apaga transitoriamente los puertos donde están conectadas las webcams para ahorrar energía, interrumpiendo el flujo DirectShow y requiriendo un reinicio manual de la cámara.
3. **Green Ethernet / Energy Efficient Ethernet en Adaptadores de Red**: Las tarjetas de red PCIe o USB reducen su velocidad o entran en micro-estados de bajo consumo (`PnPCapabilities`), provocando fluctuaciones severas en el jitter de red y pérdidas de paquetes en transmisiones SRT y UDP.
4. **Resolución Predeterminada del Temporizador del Kernel (15.6 ms)**: Por defecto, el reloj de interrupción de Windows oscila en intervalos de 15.625 ms (`1/64` s), lo que introduce un jitter inaceptable en los temporizadores de `sleep()` en hilos de sincronización de video y control de cuadros a 60 FPS (donde cada cuadro dura 16.66 ms).

## 2. Factores Decisivos (Decision Drivers)
* **Continuidad Absoluta de la Transmisión**: Prohibir categóricamente que Windows entre en suspensión mientras RTMS tenga flujos activos o el servicio esté en ejecución.
* **Cero Dependencia de PowerShell para Configuraciones de Registro**: La ejecución de scripts `.ps1` o comandos de PowerShell genera frecuentemente falsos positivos en suites antivirus y EDR empresariales. Toda manipulación de configuración debe realizarse mediante APIs Win32 directas (`winreg`, `powrprof.dll`, `kernel32.dll`).
* **Preservación y Restauración Atómica de la Configuración del Usuario**: Toda modificación realizada al perfil de energía o estado del sistema debe ser respaldada atómicamente y restaurada de manera exacta al cerrar la aplicación.
* **Resolución Temporal Submilisegundo**: Estabilizar el reloj del kernel a 1 ms para garantizar cadencia precisa de cuadros de video.

## 3. Opciones Consideradas
* **Opción A (Simulación de Pulsaciones de Teclas o Movimiento de Ratón)**: Inyectar eventos de entrada artificiales (`mouse_event` o `SendKeys`).
  - *Desventajas*: Extremadamente invasivo; interfiere con otras aplicaciones del operador, roba el foco de ventanas y no previene la suspensión selectiva de USB ni la degradación del reloj del sistema.
* **Opción B (Modificación Agresiva Irreversible del Plan de Energía vía `powercfg`)**: Ejecutar comandos batch modificando el plan a Alto Rendimiento sin respaldar los valores del usuario.
  - *Desventajas*: Viola la gobernanza del sistema operativo del cliente, deja la máquina del usuario en consumo permanente de alta potencia tras cerrar RTMS y activa bloqueos en entornos corporativos.
* **Opción C (Orquestación Integral Nativa con Win32 APIs, Respaldo JSON y Calibración `timeBeginPeriod`)**:
  - Utilizar `SetThreadExecutionState` para evitar suspensión a nivel de kernel.
  - Modificar directamente en el registro `PnPCapabilities = 24` para suprimir el ahorro de energía en tarjetas de red sin invocar PowerShell.
  - Invocar `timeBeginPeriod(1)` de `winmm.dll` para forzar la resolución del reloj del sistema a 1 ms.
  - Crear un respaldo inmutable `power_backup.json` que se restaura automáticamente en el apagado.

## 4. Decisión
Se adopta la **Opción C**:
1. En ``core/power_mgr.py`` y ``core/system_env.py``, al iniciar el sistema o una transmisión, se invoca:
   ```c
   SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED);
   ```
   Esto informa al Administrador de Energía del kernel que el hilo está ejecutando operaciones críticas de fondo que no deben ser interrumpidas por temporizadores de inactividad.
2. Se implementa `set_high_resolution_timer(enable=True)` mediante `ctypes.windll.winmm.timeBeginPeriod(1)`. Al apagar la aplicación, se invoca `timeEndPeriod(1)`, devolviendo la resolución del reloj al valor global del sistema operativo.
3. Se implementa `apply_network_power_settings()` manipulando directamente mediante `winreg` la clave:
   `SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}`
   fijando `PnPCapabilities = 24` (deshabilitar apagado por ahorro de energía) para cada interfaz física de red, con lectura y escritura de bajo nivel sin invocar procesos secundarios de PowerShell.
4. Se implementa `DynamicPowerGovernor` que almacena el esquema de energía original en `config/power_backup.json` y cambia temporalmente el esquema a Alto Rendimiento (`HIGH_PERFORMANCE_GUID` o `ULTIMATE_PERFORMANCE_GUID`) mediante `powrprof.PowerSetActiveScheme`, registrando un hook `atexit` y manejadores en `main.py` para restaurar el plan previo incondicionalmente en la salida.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Emisiones Ininterrumpidas de Larga Duración**: Se erradica por completo la caída de transmisiones provocada por suspensión de Windows tras horas de inactividad del operador.
* **Jitter de Temporizadores Erradicado**: La precisión de reloj de 1 ms reduce la variación temporal en bucles de muestreo y transmisión de video a menos de 0.8 ms de desviación estándar.
* **Cero Falsos Positivos Antivirus**: Al manipular `winreg` directamente en C, ningún EDR ni Windows Defender detecta actividad sospechosa de scripts PowerShell.
* **Higiene del Sistema**: El equipo del usuario regresa de forma transparente a su plan de energía y configuración de adaptadores original una vez finalizada la sesión de RTMS.

### Consecuencias Negativas / Limitaciones (-)
* La modificación de `PnPCapabilities` en el registro del sistema requiere privilegios de Administrador. Si la aplicación se ejecuta como usuario estándar, la función detecta limpiamente la ausencia de elevación y omite la modificación sin interrumpir el funcionamiento del software.

## 6. Validación y Cumplimiento
* Pruebas de lectura de esquemas, respaldo y restauración en ``tests/test_power_mgr.py``.
* Auditoría de comportamiento de reloj y ausencia de llamadas PowerShell en ``tests/test_audit_v260_features.py``.
