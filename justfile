# ==============================================================================
# RTMS — Real-Time Multicam System
# Recetas de automatización y build con Just runner
# ==============================================================================

# Listar todas las recetas disponibles por defecto
default:
    @just --list

# Instalar dependencias de producción en entorno local
install:
    uv pip install -e .

# Instalar dependencias de desarrollo y test
install-dev:
    uv pip install -e ".[dev]"

# Ejecutar suite completa de pruebas unitarias y de integración
test:
    pytest -v

# Ejecutar pruebas con reporte de cobertura de código
test-cov:
    pytest -v --cov=core --cov=api --cov-report=term-missing tests/

# Análisis estático y linter con Ruff
lint:
    ruff check .

# Formateo automático de código con Ruff
format:
    ruff format .

# Verificación estricta de formato sin modificar archivos
format-check:
    ruff format --check .

# Auditoría del catálogo canónico de descripciones en GitHub
check-descriptions:
    python scripts/manage_descriptions.py --check

# Sincronización automática de descripciones en GitHub vía Git commits
sync-descriptions:
    python scripts/manage_descriptions.py --sync

# Auditoría integral de salud, Git, ramas, linter y workflows
audit:
    python scripts/repo_sanitizer.py --audit

# Sanitización y corrección automática (formato, linter, descripciones y poda local)
sanitize:
    python scripts/repo_sanitizer.py --fix --prune-local --prune-env

# Auditoría, sanitización profunda y ejecución completa de pruebas
sanitize-all:
    python scripts/repo_sanitizer.py --full

# Poda de ramas locales fusionadas, referencias remotas y worktrees inactivos
prune-branches:
    python scripts/repo_sanitizer.py --prune-local --prune-env

# Construcción de empaquetado portable para Windows
build:
    cmd /c build_portable.bat

