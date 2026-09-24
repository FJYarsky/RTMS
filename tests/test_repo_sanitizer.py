# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas unitarias para el módulo de auditoría y sanitización de repositorio.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Pruebas automatizadas para scripts.repo_sanitizer."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.manage_descriptions import get_repo_root
from scripts.repo_sanitizer import (
    audit_branches,
    audit_code_quality,
    audit_descriptions,
    audit_git_status,
    audit_github_workflows,
    audit_type_checking,
    fix_code_formatting,
    fix_code_linting,
    fix_descriptions_drift,
    run_full_audit,
)


def test_audit_git_status_structure():
    """Valida que audit_git_status retorne los campos esperados del estado de Git."""
    root = get_repo_root()
    res = audit_git_status(root)
    assert "current_branch" in res
    assert "is_clean" in res
    assert "ahead_of_main" in res
    assert "behind_of_main" in res
    assert isinstance(res["uncommitted_files"], list)


def test_audit_branches_structure():
    """Valida la detección de ramas locales y remotas fusionadas."""
    root = get_repo_root()
    res = audit_branches(root)
    assert "merged_local_branches" in res
    assert "merged_remote_branches" in res
    assert "total_worktrees" in res
    # La rama activa actual nunca debe aparecer como rama a purgar
    git_st = audit_git_status(root)
    assert git_st["current_branch"] not in res["merged_local_branches"]


def test_audit_code_quality_passes():
    """Valida que la calidad de código pase en el estado actual."""
    root = get_repo_root()
    res = audit_code_quality(root)
    assert res["lint_passed"] is True
    assert res["format_passed"] is True
    assert res["status"] == "pass"


def test_audit_type_checking_passes():
    """Valida que Mypy verifique correctamente los tipos de core y api."""
    root = get_repo_root()
    res = audit_type_checking(root)
    assert res["passed"] is True
    assert res["status"] == "pass"


def test_audit_descriptions_synchronized():
    """Valida que todas las descripciones canónicas estén 100% sincronizadas."""
    root = get_repo_root()
    res = audit_descriptions(root)
    assert res["passed"] is True
    assert res["synchronized_count"] == 32
    assert len(res["drift_items"]) == 0


def test_audit_github_workflows_current():
    """Valida que los workflows actuales no contengan acciones obsoletas."""
    root = get_repo_root()
    res = audit_github_workflows(root)
    assert res["passed"] is True
    assert len(res["deprecated_actions"]) == 0


def test_audit_github_workflows_detects_deprecated():
    """Valida que audit_github_workflows detecte acciones deprecadas (ej. Node 20)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        dummy_wf = wf_dir / "old_pipeline.yml"
        dummy_wf.write_text(
            "jobs:\n  scan:\n    uses: gitleaks/gitleaks-action@v2\n",
            encoding="utf-8",
        )
        res = audit_github_workflows(tmp_path)
        assert res["passed"] is False
        assert len(res["deprecated_actions"]) == 1
        assert res["deprecated_actions"][0]["file"] == "old_pipeline.yml"
        assert "gitleaks/gitleaks-action@v3" in res["deprecated_actions"][0]["suggested"]


def test_run_full_audit_healthy():
    """Valida que run_full_audit retorne HEALTHY en el repositorio actual."""
    root = get_repo_root()
    res = run_full_audit(root, skip_tests=True)
    assert res["overall_health"] == "HEALTHY"
    assert "git_status" in res
    assert "branches" in res
    assert "code_quality" in res
    assert "type_checking" in res
    assert "descriptions" in res
    assert "github_workflows" in res


def test_fix_functions_idempotent(tmp_path: Path):
    """Valida que las funciones de autocorrección se ejecuten sin errores en un espacio aislado."""
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("x = 1\n", encoding="utf-8")
    assert fix_code_formatting(tmp_path) is True
    assert fix_code_linting(tmp_path) is True
    with patch("scripts.repo_sanitizer.audit_descriptions", return_value={"drift_items": []}):
        assert fix_descriptions_drift(tmp_path) is True
