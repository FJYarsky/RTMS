# ADR-0018: Blindaje de Seguridad en API Local, Tokens de Sesión y Mitigación Proactor

* **Fecha**: 2026-10-01
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Seguridad / API / Red / Sistema Operativo / Core
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS ejecuta un servidor HTTP FastAPI en el puerto local de la máquina (`127.0.0.1:8000+`) para proveer la interfaz de usuario y permitir el control de los flujos de video. En entornos de escritorio, los servicios expuestos en `127.0.0.1` o `localhost` están expuestos a vectores de ataque del tipo **Drive-By Localhost Exploitation / Cross-Site Request Forgery (CSRF)**:
1. Una pestaña maliciosa en el navegador del operador podría ejecutar peticiones JavaScript `fetch("http://127.0.0.1:8000/api/streams/start")` o reconfigurar las credenciales SRT del sistema.
2. Si los tokens de autenticación se transmiten por parámetros de consulta URL (*query strings*), quedan registrados en logs de acceso, historiales del navegador o cabeceras `Referer`.
3. Adicionalmente, en Windows, la implementación por defecto de `ProactorEventLoop` en Python lanza excepciones no interceptadas `ConnectionResetError: [WinError 10054]` dentro de `_ProactorBasePipeTransport` cuando un navegador o cliente WebSocket se desconecta abruptamente, inundando los registros de errores y desestabilizando el runtime asíncrono.

## 2. Factores Decisivos (Decision Drivers)
* **Protección Anti-CSRF Absoluta en Localhost**: Garantizar que solo la interfaz autorizada de RTMS (WebView2 o sesión de navegador iniciada localmente) pueda interactuar con la API de control.
* **Prohibición Categórica de Tokens en Query Strings**: Rechazar cualquier intento de autenticación que intente transmitir el token en la URL (mitigando fugas por referrers o proxies).
* **Tickets Efímeros de Un Solo Uso para Flujos Multimedia**: Permitir la carga de imágenes o streams de previsualización en elementos HTML `<img>` (que no pueden enviar cabeceras personalizadas `X-RTMS-Token`) mediante tokens efímeros criptográficos con TTL estricto y consumo atómico.
* **Estabilidad del Bucle de Eventos Proactor en Windows**: Erradicar los crashes y tracebacks espurios causados por el bug de desconexión Win32 `WSAECONNRESET / 10054`.

## 3. Opciones Consideradas
* **Opción A (Sin Autenticación por ser Localhost)**: Confiar ciegamente en que el tráfico local es inherentemente seguro.
  - *Desventajas*: Extremadamente vulnerable; cualquier script ejecutado en una página web abierta por el usuario en Chrome/Firefox podría controlar las cámaras o extraer configuraciones.
* **Opción B (Contraseña Estática Configurada por el Usuario)**: Obligar al usuario a ingresar usuario y contraseña en cada apertura.
  - *Desventajas*: Fricción inaceptable para una herramienta de producción de escritorio; no protege adecuadamente las etiquetas multimedia del navegador.
* **Opción C (Arquitectura de Seguridad Multicapa: Token Criptográfico de Sesión + Cookie HttpOnly + Tickets Efímeros + Parcheo Defensivo Proactor)**:
  - Generar un token criptográfico de alta entropía de 32 bytes (`secrets.token_urlsafe(32)`) en cada inicio de la aplicación.
  - Inyectar el token en una cookie segura HttpOnly `SameSite=Lax` y exigir la cabecera `X-RTMS-Token` en llamadas mutantes de la API.
  - Rechazar incondicionalmente (`HTTP 403`) tokens pasados por query params.
  - Implementar `PreviewTicketManager` para tickets de un solo uso con expiración en 60 segundos.
  - Parchear defensivamente `_ProactorBasePipeTransport._call_connection_lost` e instalar un manejador global de excepciones para Proactor.

## 4. Decisión
Se adopta la **Opción C**:
1. En `main.py`, se genera el token de sesión único:
   $$\text{API\_TOKEN} = \text{secrets.token\_urlsafe}(32)$$
   y se asocia al estado global de la aplicación.
2. En [`api/deps.py`](file:///C:/Users/joaqu/Desktop/RTMS/api/deps.py), el middleware de autenticación `verify_api_token()`:
   - Verifica si existe el parámetro `token` en la query string. Si está presente, lanza inmediatamente:
     $$\text{HTTP 403 Forbidden: "Token en query string prohibido por seguridad"}$$
   - Valida la cabecera `X-RTMS-Token` o la cookie `rtms_session` utilizando comparación en tiempo constante:
     `secrets.compare_digest(provided, expected_token)`
     para evitar vulnerabilidades de canal lateral basadas en tiempo (*timing attacks*).
3. **Gestor de Tickets Efímeros ([`PreviewTicketManager`](file:///C:/Users/joaqu/Desktop/RTMS/api/deps.py))**:
   - Para incrustar vistas previas en etiquetas `<img>`, el frontend solicita primero un ticket mediante `POST /api/preview/ticket`.
   - El gestor genera un token criptográfico único con TTL (60s) protegido por `threading.Lock()` y un límite máximo de 100 tickets (desalojando el más antiguo si se satura).
   - El endpoint del stream consume el ticket de forma atómica (`consume_ticket`): una vez validado, el ticket se borra de la memoria, impidiendo su reutilización (*replay attacks*).
4. **Blindaje del Bucle Proactor de Windows ([`main.py`](file:///C:/Users/joaqu/Desktop/RTMS/main.py))**:
   - Se instala `patch_proactor_connection_lost()` sobre `_ProactorBasePipeTransport._call_connection_lost` para capturar `ConnectionResetError`, `BrokenPipeError` y `WSAECONNRESET` durante el cierre de sockets de Windows.
   - Se registra `install_proactor_loop_exception_handler()` en el bucle de eventos de asyncio, silenciando los tracebacks no críticos generados cuando clientes WebSockets o navegadores cierran pestañas violentamente.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Inmunidad contra Explotación Remota Localhost**: Ataques de CSRF y scripts de terceros en el navegador son bloqueados categóricamente por la combinación de cabecera personalizada y cookie `SameSite=Lax`.
* **Cero Fugas de Credenciales en Logs**: La prohibición de tokens en query strings garantiza que ningún proxy o registro de depuración filtre el secreto de sesión.
* **Sesiones de Previsualización Seguras y Efímeras**: Los tickets de un solo uso eliminan vectores de persistencia no autorizada de transmisiones de video.
* **Logs Limpios y Estabilidad de Sockets**: Erradicación del 100% de los molestos volcados de traceback de WinError 10054 en la consola de Windows.

### Consecuencias Negativas / Limitaciones (-)
* Desarrolladores o integradores de scripts externos que deseen automatizar RTMS vía API REST deben obtener el token de sesión o utilizar los métodos autorizados de autenticación mediante cabecera HTTP.

## 6. Validación y Cumplimiento
* Pruebas de rechazo de query string y autenticación por cabecera en [`tests/test_audit_security.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_security.py).
* Verificación del gestor de tickets efímeros y consumo atómico en [`tests/test_audit_preview.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_preview.py).
* Pruebas de desconexión abrupta y robustez de Proactor en [`tests/test_fuzzing_and_boundaries.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_fuzzing_and_boundaries.py).
