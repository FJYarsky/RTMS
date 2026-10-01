# ADR-0011: Cifrado en Reposo de Secretos y Passphrases mediante Windows DPAPI

* **Fecha**: 2026-10-01
* **Estado**: Aceptado (Extiende y complementa el cifrado en tránsito de ADR-0003)
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Seguridad / Criptografía / Reposo de Datos / Core
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
El estándar ADR-0003 estableció el cifrado simétrico AES-128 para el transporte de flujos de video mediante el protocolo SRT, protegiendo las señales de video en tránsito. Sin embargo, dicho registro no definió la política de almacenamiento para las frases de paso (*passphrases*) y tokens de autenticación cuando se persisten en disco dentro de la configuración del sistema.

Almacenar frases de paso en texto plano dentro de la base de datos `rtms.db` o archivos de configuración expone las credenciales ante:
1. Volcados involuntarios de configuración compartidos en reportes de soporte técnico o incidencias públicas en GitHub.
2. Lectura no autorizada por malware en espacio de usuario o usuarios secundarios sin privilegios que tengan acceso al sistema de archivos local.
3. Extracción de secretos durante auditorías forenses o copias de respaldo desprotegidas.

## 2. Factores Decisivos (Decision Drivers)
* **Cero Almacenamiento en Texto Plano**: Ninguna frase de paso SRT debe persistirse en texto legible en disco bajo ninguna circunstancia.
* **Sin Gestión de Claves Maestras por el Usuario**: Evitar exigir al usuario memorizar o configurar una contraseña maestra adicional en cada arranque del sistema, lo cual impediría el funcionamiento de la aplicación en modo servicio desatendido o autoarranque con Windows.
* **Atadura Criptográfica a la Identidad del Usuario del Sistema Operativo**: El secreto debe estar cifrado utilizando una clave derivada criptográficamente por el kernel y protegida por las credenciales de inicio de sesión del usuario de Windows.
* **Fallo Seguro (Fail-Secure)**: Si el mecanismo de cifrado no está operativo en un entorno de producción, la operación de persistencia debe ser rechazada de inmediato en lugar de degradar silenciosamente a texto plano.

## 3. Opciones Consideradas
* **Opción A (Ofuscación mediante Base64 o Cifrado con Clave Simétrica Estática en Código Fuente)**:
  - *Desventajas*: Seguridad por oscuridad trivialmente eludible; cualquier atacante o desensamblador del ejecutable puede extraer la clave estática y descifrar la base de datos completa.
* **Opción B (Cifrado con Contraseña Maestra Solicitada en el Arranque)**:
  - *Desventajas*: Destruye el caso de uso fundamental de RTMS de arrancar de manera desatendida al inicio del sistema operativo (headless/autostart).
* **Opción C (Windows Data Protection API - DPAPI mediante `CryptProtectData` y `CryptUnprotectData`)**:
  - *Ventajas*: Utiliza las primitivas criptográficas nativas del kernel de Windows. La clave de cifrado se deriva del hash de credenciales del usuario actual de Windows y las claves de seguridad LSA (Local Security Authority). Solo el proceso ejecutándose bajo la misma cuenta de usuario puede descifrar los datos.

## 4. Decisión
Se adopta la **Opción C**:
1. Se crea el módulo de seguridad [`core/secrets_mgr.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/secrets_mgr.py) que interactúa con la API Win32 de `crypt32.dll` utilizando `ctypes`.
2. Para cifrar un secreto, se invoca `CryptProtectData` empaquetando el texto plano en una estructura `DATA_BLOB`. El buffer cifrado resultante se codifica en Base64 y se le añade el prefijo canónico inmutable `dpapi:` (ej. `dpapi:AQAAANCMnd8BFdERjHoAwE...`).
3. Para descifrar un secreto para uso en memoria (ej. inyección de flags a FFmpeg o MediaMTX), `unprotect_secret()` verifica el prefijo `dpapi:`, decodifica el Base64 e invoca `CryptUnprotectData`.
4. **Política de Fallo Seguro**: Si en un entorno Windows la llamada a DPAPI falla o no está disponible, la función `protect_secret()` lanza una excepción `SecretEncryptionError`, impidiendo de forma categórica que la credencial sea guardada en la base de datos en texto plano.
5. **Máscara en la Capa de Presentación**: En las APIs REST ([`api/routes/config.py`](file:///C:/Users/joaqu/Desktop/RTMS/api/routes/config.py)) y la interfaz gráfica, cualquier secreto configurado se oculta bajo la máscara `••••••••`. El usuario puede conservarlo (`secret_action: "keep"`), reemplazarlo (`secret_action: "set"`) o eliminarlo (`secret_action: "clear"`), sin que el valor descifrado sea transmitido jamás por la API REST hacia el navegador.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Confidencialidad Robusta en Reposo**: Si el archivo de base de datos `rtms.db` es sustraído o exportado, los secretos permanecen matemáticamente inaccesibles sin las claves privadas del perfil de Windows del usuario emisor.
* **Arranque Desatendido Ininterrumpido**: El servicio puede iniciar automáticamente tras el arranque de Windows sin interacción humana ni solicitudes de contraseña maestra.
* **Prevención de Exfiltración por API**: Los tokens y passphrases jamás viajan en respuestas HTTP JSON en texto claro.

### Consecuencias Negativas / Limitaciones (-)
* Los datos cifrados con DPAPI están vinculados al usuario local de Windows. Si la base de datos se traslada físicamente a otra máquina o se ejecuta bajo otra cuenta de usuario de Windows, `CryptUnprotectData` retornará fallo, requiriendo reingresar las claves (diseño deliberado de contención de seguridad).
* En entornos de prueba no-Windows (Linux CI), el sistema opera en modo fallback simulado para permitir la ejecución de la suite de tests automatizados.

## 6. Validación y Cumplimiento
* Pruebas criptográficas de cifrado, descifrado y rechazo de degradación en [`tests/test_secrets_mgr.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_secrets_mgr.py).
* Auditoría de seguridad de endpoints REST y enmascaramiento en [`tests/test_audit_security.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_security.py).
