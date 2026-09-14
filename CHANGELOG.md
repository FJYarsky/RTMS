# Changelog — RTMS (Real-Time Multicam System)

Todas las modificaciones notables de este proyecto se documentan en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y el versionado sigue [Semantic Versioning](https://semver.org/lang/es/).

---

## [2.0.3] — 2026-09-14

### Seguridad y Hardening
- **CORS Restringido**: Eliminado el comodín `allow_origins=["*"]` con credenciales. Ahora restringido estrictamente al origen dinámico local `http://127.0.0.1:<puerto>` para blindar la API contra ataques Localhost CSRF / Drive-by.
- **Autenticación por Token Local (`X-RTMS-Token`)**: Generación de un token criptográfico de sesión (`secrets.token_urlsafe(32)`) inyectado en el frontend nativo y exigido como cabecera obligatoria en todos los endpoints de modificación de estado (`POST /api/*`).
- **Enmascaramiento de Contraseñas SRT**: La API `/api/status` ya no expone la `srt_passphrase` en texto plano, devolviendo en su lugar `"••••••••"` y el indicador `has_passphrase: true`.
- **Passphrase Segura por Defecto**: Las nuevas cámaras creadas con protocolo SRT generan automáticamente una contraseña segura aleatoria de 12 caracteres (`secrets.token_hex(6)`).
- **Higiene de Repositorio**: Exclusión de `config/config.json` con datos de hardware local de Git mediante `.gitignore` y provisión de `config/config.example.json` limpio.

### Robustez del Watchdog
- **Reseteo de Errores por Estabilidad**: Si un flujo opera de forma ininterrumpida en estado `RUNNING` durante más de 60 segundos, su contador `error_count` se resetea a 0 automáticamente.
- **Verificación de Desconexión Física**: Si una cámara USB es desenchufada (`is_connected == False`), el Watchdog pausa los reintentos hasta que el sondeo periódico de hardware verifique su reconexión.
- **Backoff Exponencial**: Intervalos progresivos de reintento ante fallos sucesivos (5s, 10s, 20s, 40s, hasta un máximo de 60s).

### Calidad de Código y Estabilidad
- **Rotación de Logs (`RotatingFileHandler`)**: Reemplazado `FileHandler` por rotación de archivos de 5 MB con 3 copias de seguridad para prevenir crecimiento indefinido en ejecuciones 24/7.
- **Endpoint de Salud (`/healthz`)**: Implementado endpoint ligero para supervisores de procesos del sistema operativo.
- **Suite de Pruebas Automatizadas**: Integración de `pytest` con tests unitarios para análisis de DirectShow, configuración y seguridad de la API.
- **Pipeline de Integración Continua (CI)**: Flujo de trabajo de GitHub Actions en `.github/workflows/ci.yml`.

---

## [2.0.2] — 2026-09-14

### Agregado
- Protocolo SRT por defecto con ultra baja latencia (`zerolatency`).
- Conversión universal a `-pix_fmt yuv420p` en FFmpeg para compatibilidad total con GPU (NVENC, AMF, QSV).
- Bloqueo de instancia única con Win32 Named Mutex (`single_instance.py`).
- Autoarranque desatendido individual por cámara con sincronización continua PnP.
- Minimización a la bandeja del sistema de Windows (*System Tray*) mediante `pystray`.
- Telemetría en vivo en Header (CPU %, RAM %, Bitrate) y FPS/Bitrate real por cámara.
- Botón rojo de parada de emergencia con apagado seguro (*graceful shutdown*).
- Sección colapsable para cámaras virtuales y secundarias.
- Modal "Acerca de" con información y enlaces oficiales de Joaquín Yarsky.

---

## [2.0.0] — 2026-07-03

### Versión Inicial
- Arquitectura desacoplada FastAPI + `pywebview` + FFmpeg DirectShow.
- Soporte básico de UDP Multicast y SRT.
- Optimizaciones de energía en Windows y reglas de firewall.
