# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas automatizadas de integridad de ADRs y RFCs
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de validación de conformidad y estructura de ADRs y RFCs."""

from pathlib import Path


def test_adr_catalog_and_files_integrity():
    """Valida que todos los ADRs existan, sigan la nomenclatura estándar y contengan secciones requeridas."""
    repo_root = Path(__file__).parent.parent
    adr_dir = repo_root / "docs" / "adr"
    assert adr_dir.is_dir(), "El directorio docs/adr no existe"

    readme_path = adr_dir / "README.md"
    assert readme_path.is_file(), "El índice docs/adr/README.md no existe"
    readme_content = readme_path.read_text(encoding="utf-8")

    adr_files = sorted([f for f in adr_dir.glob("*.md") if f.name not in ["README.md", "template.md"]])
    assert len(adr_files) >= 8, f"Se esperaban al menos 8 ADRs, encontrados: {len(adr_files)}"

    required_sections = [
        "## 1. Contexto",
        "## 2. Factores Decisivos",
        "## 4. Decisión",
        "## 5. Consecuencias",
    ]

    for adr_file in adr_files:
        content = adr_file.read_text(encoding="utf-8")
        assert adr_file.name in readme_content, f"{adr_file.name} no está referenciado en docs/adr/README.md"
        for sec in required_sections:
            assert sec in content, f"{adr_file.name} carece de la sección obligatoria: '{sec}'"


def test_rfc_catalog_and_files_integrity():
    """Valida que todos los RFCs existan, sigan la nomenclatura estándar y contengan secciones requeridas."""
    repo_root = Path(__file__).parent.parent
    rfc_dir = repo_root / "docs" / "rfc"
    assert rfc_dir.is_dir(), "El directorio docs/rfc no existe"

    readme_path = rfc_dir / "README.md"
    assert readme_path.is_file(), "El índice docs/rfc/README.md no existe"
    readme_content = readme_path.read_text(encoding="utf-8")

    rfc_files = sorted([f for f in rfc_dir.glob("*.md") if f.name not in ["README.md", "template.md"]])
    assert len(rfc_files) >= 2, f"Se esperaban al menos 2 RFCs, encontrados: {len(rfc_files)}"

    required_sections = [
        "## 1. Resumen",
        "## 2. Motivación",
        "## 3. Especificación Detallada",
    ]

    for rfc_file in rfc_files:
        content = rfc_file.read_text(encoding="utf-8")
        assert rfc_file.name in readme_content, f"{rfc_file.name} no está referenciado en docs/rfc/README.md"
        for sec in required_sections:
            assert sec in content, f"{rfc_file.name} carece de la sección obligatoria: '{sec}'"
