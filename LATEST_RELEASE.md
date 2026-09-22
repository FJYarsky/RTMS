# RTMS v2.4.0 — Arquitectura Limpia, Descomposición Modular sin Fachadas, Tooling Determinista y Cierre de Fase 1

**Fecha:** 22 de Septiembre de 2026 | **Versión:** `v2.4.0`

---

### 🏗️ Arquitectura Limpia y Descomposición Modular (Cierre de Fase 1)
- **Eliminación Total de Monolitos**:
  - `core/ffmpeg_mgr.py` (813 líneas) descompuesto y reemplazado en su totalidad por 4 módulos de responsabilidad única:
    - `core/stream_proc.py`: Estados (`State`), categorías de error (`ErrorCategory`), construcción de URLs y proceso individual `StreamProc`.
    - `core/command_builder.py`: Constructor puro de comandos FFmpeg, mapeo de resoluciones y perfiles zerolatency.
    - `core/hardware_sync.py`: Sincronización periódica y manual de hardware DirectShow con el inventario de cámaras.
    - `core/stream_manager.py`: Orquestador `StreamManager`, watchdog asíncrono y singleton central.
  - `api/routes.py` (797 líneas) transformado en el paquete canónico de FastAPI `api/routes/` (`health.py`, `streams.py`, `preview.py`, `config.py`, `system.py`, `power.py`) junto con `api/deps.py`.
- **Cero Fachadas Residuales**: Prescindido de intermediarios o capas obsoletas. Resolución directa de módulos sin envoltorios artificiales.

---

### 🛡️ Erradicación Total de "Mock Drift" en Tests
- Actualización del 100% de la suite de pruebas unitarias y de integración:
  - Cada test importa y mockea directamente el submódulo de destino donde se ejecuta la lógica (`core.stream_proc`, `core.stream_manager`, `api.routes.preview`, `api.routes.streams`, `api.deps`).
  - Garantía de evaluación fidedigna del comportamiento de ejecución, sin riesgo de falsos positivos.

---

### 📦 Tooling Determinista y Catálogo Oficial
- **`justfile`**: Recetas estándar de automatización de desarrollo (`install`, `test`, `lint`, `format`, `build`).
- **`.pre-commit-config.yaml`**: Hooks locales de pre-commit para linters y formateo con Ruff.
- **`uv.lock`**: Resolución determinista de dependencias del proyecto.
- **Catálogo Canónico GitHub**: Dimensionamiento y preservación estricta de 31 elementos raíz oficiales sin truncamiento ni drift.
