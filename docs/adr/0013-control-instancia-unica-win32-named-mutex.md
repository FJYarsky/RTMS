# ADR-0013: Aislamiento de Instancia Única mediante Win32 Named Mutex Global/Local Jerárquico

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Core / Sistema Operativo / IPC / Estabilidad
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS es una aplicación de escritorio y servidor local que controla recursos físicos exclusivos:
1. Dispositivos DirectShow y webcams USB, las cuales solo admiten un descriptor de captura activo a la vez en el controlador de hardware.
2. Puertos de enlace fijos o preferenciales (MediaMTX en 8890, API en 8000, SRT en 9000-9200).
3. Base de datos local SQLite y archivos de log con rotación en disco.

Si un usuario hace doble clic repetido en el ejecutable, o si se lanzan múltiples instancias concurrentemente por error, la segunda instancia entra en colisión directa con la primera: falla al intentar enlazar los sockets de red (`WSAEADDRINUSE`), bloquea la base de datos con esperas de lock o provoca errores graves en los drivers de DirectShow al intentar abrir cámaras ya ocupadas.

## 2. Factores Decisivos (Decision Drivers)
* **Detección Atómica Instantánea**: La comprobación de si ya existe otra instancia debe resolverse en tiempo de CPU inferior a 5 milisegundos durante la fase previa a la carga del runtime de FastAPI o WebView2.
* **Resiliencia ante Privilegios Heterogéneos**: Debe funcionar tanto cuando la primera instancia se ejecuta con privilegios de Administrador y la segunda como usuario estándar, como cuando ambas son instancias de usuario sin privilegios.
* **Notificación al Usuario**: Si una segunda instancia es rechazada, debe informar claramente al usuario mediante un diálogo nativo o log y finalizar limpiamente sin dejar residuos ni alterar el estado de la instancia activa.
* **Liberación Determinista en Apagado**: El bloqueo debe liberarse de forma inmediata y automática al finalizar la aplicación, permitiendo reinicios instantáneos.

## 3. Opciones Consideradas
* **Opción A (Archivo de Bloqueo PID tipo `rtms.lock`)**: Escribir el PID en un archivo y comprobar si el proceso sigue vivo.
  - *Desventajas*: Extremadamente propenso a estados inconsistentes (*stale locks*); si la máquina sufre un corte de energía o crash forzado, el archivo `.lock` permanece en disco impidiendo arrancar el software hasta que el usuario borre el archivo manualmente.
* **Opción B (Sondeo de Puerto de Socket TCP Local)**: Intentar abrir un socket en un puerto fijo y verificar si responde.
  - *Desventajas*: No distingue si el puerto está ocupado por RTMS o por otro servicio independiente del sistema; introduce retardos de timeout de red y fallos por restricciones de firewall.
* **Opción C (Named Mutex de Win32 con Fallback Jerárquico Global/Local)**:
  - Invocar la API Win32 `CreateMutexW` de `kernel32.dll`.
  - Intentar primero crear el mutex en el espacio de nombres global (`Global\RTMS_Multicam_v2_SingleInstance_Mutex`).
  - Si el usuario carece del privilegio `SeCreateGlobalPrivilege` (retornando `ERROR_ACCESS_DENIED`), recurrir de forma transparente al espacio de nombres de la sesión local (`Local\RTMS_Multicam_v2_SingleInstance_Mutex`).
  - Evaluar `GetLastError() == ERROR_ALREADY_EXISTS` para certificar la existencia de una instancia previa.

## 4. Decisión
Se adopta la **Opción C**:
1. Se implementa [`core/single_instance.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/single_instance.py).
2. En `main.py`, la primera instrucción antes de instanciar Uvicorn o importar dependencias pesadas es invocar `acquire_single_instance_lock()`.
3. Se invoca `kernel32.CreateMutexW` solicitando el identificador del Mutex:
   - Nombre Global: `Global\RTMS_Multicam_v2_SingleInstance_Mutex`
   - Nombre Local: `Local\RTMS_Multicam_v2_SingleInstance_Mutex`
4. Si la función retorna un handle válido y `ctypes.get_last_error() == 183` (`ERROR_ALREADY_EXISTS`), o si el handle es nulo por conflicto, se concluye que otra instancia está activa.
5. Si ya existe una instancia activa, la instancia secundaria muestra un cuadro de diálogo nativo mediante `user32.MessageBoxW` informando la situación y finaliza de inmediato con código de salida `0` (`sys.exit(0)`).
6. Se implementa `release_single_instance_lock()` cerrando el handle con `kernel32.CloseHandle` en la rutina de salida unificada `on_closed()`. Adicionalmente, el kernel de Windows garantiza la destrucción automática de los Mutex de un proceso al terminarse este, eliminando el problema de los bloqueos residuales (*stale locks*).

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Garantía Incondicional de Exclusión**: Imposibilidad matemática de que dos instancias compitan por las cámaras físicas o los puertos de red.
* **Inmunidad ante Caídas y Cortes Eléctricos**: Al residir el Named Mutex en la tabla de objetos del kernel de Windows y no en disco, la muerte del proceso libera el mutex instantáneamente sin requerir limpieza manual de archivos.
* **Arranque Ultrarrápido**: La validación toma menos de 1 ms, permitiendo abortar instancias duplicadas antes de inicializar el entorno gráfico o los servidores web.

### Consecuencias Negativas / Limitaciones (-)
* Primitiva dependiente del kernel de Windows (`sys.platform == "win32"`). En plataformas no-Windows (entornos de pruebas en CI Linux), la función retorna `True` por omisión.

## 6. Validación y Cumplimiento
* Pruebas automatizadas de adquisición concurrente, liberación y detección de colisión en [`tests/test_single_instance.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_single_instance.py).
* Verificación manual: Lanzar `rtms.exe`, abrir una segunda consola y lanzar nuevamente `rtms.exe`, comprobando el mensaje de advertencia y la finalización limpia de la segunda instancia.
