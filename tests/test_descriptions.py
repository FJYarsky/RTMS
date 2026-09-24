# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de auditoría y catálogo de descripciones canónicas en GitHub.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de auditoría y catálogo de descripciones canónicas en GitHub."""

import pytest

from scripts.manage_descriptions import (
    DESCRIPTIONS_CATALOG,
    get_repo_root,
    is_canonical_match,
    is_shallow_repo,
    run_check,
)


def test_catalog_completeness():
    """Valida que el catálogo contenga exactamente los 32 elementos raíz oficiales."""
    assert len(DESCRIPTIONS_CATALOG) == 32
    expected_directories = [".github", "api", "config", "core", "docs", "gui", "scripts", "site", "tests"]
    for d in expected_directories:
        assert d in DESCRIPTIONS_CATALOG


def test_catalog_string_lengths_and_format():
    """Valida que cada descripción cumpla con la longitud (<45 chars) y formato <categoria>: <texto>."""
    for item, desc in DESCRIPTIONS_CATALOG.items():
        assert len(desc) <= 45, f"Descripción para '{item}' excede 45 caracteres ({len(desc)}): '{desc}'"
        assert len(desc) >= 20, f"Descripción para '{item}' es demasiado corta ({len(desc)}): '{desc}'"
        assert ": " in desc, f"Descripción para '{item}' debe seguir el formato '<categoria>: <texto>': '{desc}'"
        assert "..." not in desc, f"Descripción para '{item}' no debe contener puntos suspensivos: '{desc}'"


def test_get_repo_root_exists():
    """Valida que la función localice la raíz del repositorio correctamente."""
    root = get_repo_root()
    assert root.exists()
    assert (root / "main.py").exists()
    assert (root / "pyproject.toml").exists()


def test_run_check_current_repository():
    """Valida que el repositorio actual reporte 100% de sincronización con el catálogo."""
    if is_shallow_repo():
        pytest.skip("Repositorio clonado superficialmente (shallow clone). Se requiere historial completo.")
    result = run_check()
    assert result == 0


def test_is_canonical_match_tolerance():
    """Valida que se toleren sufijos de squash-merge de GitHub manteniendo rechazo de desvíos reales."""
    canonical = "web: sitio oficial y portal de descargas"
    assert is_canonical_match(canonical, canonical)
    assert is_canonical_match(f"{canonical} (#24)", canonical)
    assert is_canonical_match(f"{canonical} (#999)", canonical)
    assert not is_canonical_match("web: sitio desactualizado", canonical)
    assert not is_canonical_match("chore: random change (#12)", canonical)
