# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas de integridad para la GitHub Wiki.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas unitarias y de integración para la GitHub Wiki de RTMS."""

from pathlib import Path

from scripts.sync_wiki import (
    _WIKI_SRC_DIR,
    build_wiki_distribution,
    get_wiki_slug,
    validate_wiki_integrity,
)


def test_wiki_slug_generation():
    """Valida la generación determinista de slugs canónicos para GitHub Wiki."""
    assert get_wiki_slug("0001-adopcion-mediamtx-broker-central.md") == "ADR-0001-Adopcion-Mediamtx-Broker-Central"
    assert (
        get_wiki_slug("0008-sanitizacion-datos-sensibles-y-descripciones-canonicas.md")
        == "ADR-0008-Sanitizacion-Datos-Sensibles-y-Descripciones-Canonicas"
    )
    assert (
        get_wiki_slug("RFC-0001-protocolo-verificacion-e2e-y-benchmark-optico.md")
        == "RFC-0001-Protocolo-Verificacion-E2e-y-Benchmark-Optico"
    )
    assert get_wiki_slug("c4-system-architecture.md") == "C4-System-Architecture"


def test_wiki_mandatory_files_exist():
    """Verifica que los archivos estructurales obligatorios de la Wiki existan."""
    assert (_WIKI_SRC_DIR / "Home.md").exists(), "Home.md debe existir en docs/wiki/"
    assert (_WIKI_SRC_DIR / "_Sidebar.md").exists(), "_Sidebar.md debe existir en docs/wiki/"
    assert (_WIKI_SRC_DIR / "_Footer.md").exists(), "_Footer.md debe existir en docs/wiki/"
    assert (_WIKI_SRC_DIR / "Guia-de-Inicio-Rapido.md").exists()
    assert (_WIKI_SRC_DIR / "Catalogo-de-ADRs.md").exists()
    assert (_WIKI_SRC_DIR / "Catalogo-de-RFCs.md").exists()


def test_wiki_adrs_and_rfcs_coverage():
    """Verifica que los 24 ADRs y los 6 RFCs cuenten con su página wiki correspondiente."""
    wiki_files = {p.name for p in _WIKI_SRC_DIR.glob("*.md")}

    # Validar que los 24 ADRs estén presentes
    for i in range(1, 25):
        prefix = f"ADR-{i:04d}-"
        matching = [name for name in wiki_files if name.startswith(prefix)]
        assert len(matching) == 1, f"El registro ADR {i:04d} debe tener exactamente una página en la wiki."

    # Validar que los 6 RFCs estén presentes
    for i in range(1, 7):
        prefix = f"RFC-{i:04d}-"
        matching = [name for name in wiki_files if name.startswith(prefix)]
        assert len(matching) == 1, f"La propuesta RFC {i:04d} debe tener exactamente una página en la wiki."


def test_wiki_integrity_and_no_broken_links(tmp_path: Path):
    """Verifica la compilación y que no existan enlaces rotos en la Wiki."""
    # Compilar a directorio temporal
    build_dir = tmp_path / "wiki_build"
    compiled_files = build_wiki_distribution(dest_dir=build_dir)
    assert len(compiled_files) >= 30, "La wiki debe compilar al menos 30 páginas de documentación."

    # Validar integridad
    is_valid, errors, warnings = validate_wiki_integrity(build_dir)
    assert is_valid, f"Se detectaron errores de integridad en la wiki: {errors}"
    assert len(errors) == 0, f"No deben existir enlaces rotos: {errors}"
