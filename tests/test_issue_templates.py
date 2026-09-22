# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas de validación de Issue Templates y Política de Seguridad de GitHub.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas de validación de Issue Templates y Política de Seguridad de GitHub."""

import re

import yaml

from scripts.manage_descriptions import get_repo_root


def test_issue_template_directory_exists():
    """Valida que el directorio .github/ISSUE_TEMPLATE exista en el repositorio."""
    root = get_repo_root()
    issue_dir = root / ".github" / "ISSUE_TEMPLATE"
    assert issue_dir.exists()
    assert issue_dir.is_dir()


def test_config_yml_structure():
    """Valida que config.yml deshabilite issues en blanco y contenga enlaces de contacto."""
    root = get_repo_root()
    config_file = root / ".github" / "ISSUE_TEMPLATE" / "config.yml"
    assert config_file.exists()

    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert data.get("blank_issues_enabled") is False
    assert "contact_links" in data
    assert len(data["contact_links"]) >= 2
    for link in data["contact_links"]:
        assert "name" in link
        assert "url" in link
        assert "about" in link


def test_issue_forms_valid_yaml_and_schema():
    """Valida que todas las plantillas .yml cumplan con la especificación de GitHub Issue Forms."""
    root = get_repo_root()
    issue_dir = root / ".github" / "ISSUE_TEMPLATE"

    expected_templates = ["bug.yml", "feature.yml", "hardware-compatibility.yml", "documentation.yml"]
    allowed_types = {"markdown", "textarea", "input", "dropdown", "checkboxes"}

    for tmpl in expected_templates:
        path = issue_dir / tmpl
        assert path.exists(), f"Falta plantilla requerida: {tmpl}"

        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        assert "name" in data, f"'{tmpl}' debe tener campo 'name'"
        assert "description" in data, f"'{tmpl}' debe tener campo 'description'"
        assert "title" in data, f"'{tmpl}' debe tener campo 'title'"
        assert "labels" in data and isinstance(data["labels"], list), f"'{tmpl}' debe tener campo 'labels' tipo lista"
        assert "body" in data and isinstance(data["body"], list), f"'{tmpl}' debe tener campo 'body' tipo lista"

        for field in data["body"]:
            assert "type" in field, f"Elemento en body de '{tmpl}' carece de 'type'"
            assert field["type"] in allowed_types, f"Tipo '{field['type']}' no permitido en '{tmpl}'"
            assert "attributes" in field, f"Elemento '{field.get('id')}' en '{tmpl}' carece de 'attributes'"


def test_security_md_supported_versions():
    """Valida que SECURITY.md estipule soporte exclusivamente desde la versión actual en pyproject.toml en adelante."""
    root = get_repo_root()
    sec_file = root / "SECURITY.md"
    pyproject_file = root / "pyproject.toml"
    assert sec_file.exists()
    assert pyproject_file.exists()

    pyproject_content = pyproject_file.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
    assert match is not None
    current_version = re.escape(match.group(1))

    content = sec_file.read_text(encoding="utf-8")
    assert re.search(rf"\|\s*>=\s*{current_version}\s*\|\s*:white_check_mark:\s*\|", content)
    assert re.search(rf"\|\s*<\s*{current_version}\s*\|\s*:x:\s*\|", content)


def test_release_workflow_updates_security_md():
    """Valida que el pipeline de release contenga el paso de actualización de SECURITY.md."""
    root = get_repo_root()
    rel_file = root / ".github" / "workflows" / "release.yml"
    assert rel_file.exists()

    content = rel_file.read_text(encoding="utf-8")
    assert "Update SECURITY.md Supported Version" in content
    assert "SECURITY.md" in content
    assert "manage_descriptions.py --commit" in content
