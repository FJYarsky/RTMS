# ADR-0006: Desacoplamiento de FastAPI Asíncrono, GUI Web y System Tray Nativo

* **Fecha**: 2026-09-16
* **Estado**: Reemplazado por [ADR-0019](0019-interfaz-nativa-escritorio-webview2-bandeja-sistema.md)
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: GUI / Core / Concurrencia
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
RTMS se concibió como un sistema que combina un servidor de streaming en segundo plano (FastAPI + Uvicorn asíncrono sobre `asyncio`) con una interfaz de usuario accesible vía navegador web y una bandeja de sistema nativa (System Tray con icono interactivo y menú contextual en la barra de tareas de Windows).

En Windows, el bucle de mensajes de la interfaz gráfica nativa (`Win32 Message Loop` o `pystray`) requiere ejecutarse de forma sincrónica en el hilo principal o en un hilo dedicado con bombeo constante de mensajes (`PumpMessages`), lo cual colisionaba y bloqueaba el bucle asíncrono de eventos `asyncio` de Uvicorn si no se desacoplaban adecuadamente.

## 2. Factores Decisivos (Decision Drivers)
* **No Bloqueo del Motor de Streaming**: El renderizado de la UI o la interacción con el System Tray nunca debe congelar la captura ni el procesamiento de paquetes de video.
* **Operación Headless Opcional**: Capacidad de ejecutar el software como servicio en segundo plano sin ventana gráfica ni icono de bandeja (modo servidor).
* **Cierre y Reinicio Limpio**: Los eventos de suspensión del sistema (Sleep/Hibernate), cierre de sesión o reinicio deben liberar los recursos de hardware ordenadamente.

## 3. Opciones Consideradas
* **Opción A (Framework GUI pesado como PyQt/PySide o Electron)**: Interfaz rica pero peso de distribución gigantesco (>150 MB de dependencias adicionales), complejidad de licenciamiento y consumo innecesario de RAM.
* **Opción B (Servidor Web puro sin System Tray)**: Simple, pero mala experiencia para el usuario común de Windows al carecer de icono de notificación y control rápido de salida.
* **Opción C (Arquitectura Híbrida: Backend FastAPI Asíncrono + GUI Web Ligera + System Tray en hilo dedicado con pystray)**: FastAPI corre en el bucle asíncrono principal; el System Tray corre en un hilo secundario aislado comunicándose mediante eventos y llamadas no bloqueantes.

## 4. Decisión
Se implementa la **Opción C**:
1. El backend corre sobre **FastAPI** y **Uvicorn**, exponiendo endpoints REST y WebSockets para telemetría en tiempo real.
2. La interfaz de usuario es una **Single-Page Application (SPA)** moderna, ligera y responsiva servida directamente desde [`gui/index.html`](file:///C:/Users/joaqu/Desktop/RTMS/gui/index.html) sin empaquetadores externos.
3. El módulo [`core/tray.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/tray.py) administra el System Tray en un hilo desacoplado usando `pystray` y `Pillow`, interactuando con [`core/stream_manager.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/stream_manager.py) a través de métodos seguros con locks.
4. El módulo [`core/power_mgr.py`](file:///C:/Users/joaqu/Desktop/RTMS/core/power_mgr.py) escucha los eventos de energía de Windows para pausar y reanudar flujos de video limpiamente.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Máxima Ligereza**: Peso total del ejecutable y dependencias mínimo (<40 MB de RAM).
* **Acceso Remoto y Local Unificado**: El usuario puede controlar las cámaras desde la misma PC o desde cualquier teléfono/tablet conectado a la misma red local mediante su navegador web.
* **Resiliencia**: Si el navegador se cierra, los flujos continúan emitiendo sin interrupción en segundo plano.

### Consecuencias Negativas / Limitaciones (-)
* En entornos sin servidor gráfico (como contenedores Docker puros de Linux o servidores sin interfaz), el System Tray debe inicializarse en modo silencioso (`headless: True`).

## 6. Validación y Cumplimiento
* Pruebas de integración de ciclo de vida en [`tests/test_audit_lifecycle.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_audit_lifecycle.py) y [`tests/test_tray.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_tray.py).
* Verificación de concurrencia y estrés en [`tests/test_stress_concurrency.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_stress_concurrency.py).
