# ==============================================================================
# RTMS — Real-Time Multicam System
# Automatización de auditoría, corrección y sanitización integral del repositorio.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Herramienta integral de auditoría, corrección automática y sanitización de RTMS."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.manage_descriptions import (
    DESCRIPTIONS_CATALOG,
    get_latest_commit_subject,
    get_repo_root,
    is_canonical_match,
    run_restore,
)

# Acciones de GitHub conocidas con versiones obsoletas / deprecadas (ej. runtime Node 20)
DEPRECATED_GITHUB_ACTIONS: Dict[str, Tuple[str, str]] = {
    r"gitleaks/gitleaks-action@v[12]\b": (
        "gitleaks/gitleaks-action@v3",
        "Deprecación de Node 20; requiere v3 para Node 24",
    ),
    r"actions/configure-pages@v[1-5]\b": (
        "actions/configure-pages@v6",
        "Deprecación de Node 20; requiere v6 para Node 24",
    ),
    r"actions/upload-pages-artifact@v[1-4]\b": (
        "actions/upload-pages-artifact@v5",
        "Deprecación de Node 20; requiere v5 para Node 24",
    ),
    r"crazy-max/ghaction-virustotal@v[1-4]\b": (
        "crazy-max/ghaction-virustotal@v5",
        "Deprecación de Node 20; requiere v5 para Node 24",
    ),
    r"github/codeql-action/(upload-sarif|analyze|init)@v[1-3]\b": (
        "github/codeql-action/upload-sarif@v4",
        "Actualización recomendada a CodeQL Action v4",
    ),
}


def _run_cmd(cmd: List[str], cwd: Path, check: bool = False, timeout: int = 120) -> Tuple[int, str, str]:
    """Ejecuta un comando del sistema y captura su código de salida, stdout y stderr."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=check,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Comando '{' '.join(cmd)}' expiró tras {timeout}s."
    except Exception as e:
        return 1, "", str(e)


# ==============================================================================
# SECCIÓN 1: AUDITORÍA (CHECKS)
# ==============================================================================


def audit_git_status(repo_root: Path) -> Dict[str, Any]:
    """Audita el estado del árbol de trabajo de Git y la sincronización con origin/main."""
    code, branch, _ = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    code_stat, porcelain, _ = _run_cmd(["git", "status", "--porcelain"], repo_root)
    uncommitted = [line for line in porcelain.splitlines() if line.strip()]

    # Verificar si origin/main existe para chequear commits desfasados
    code_sync, sync_info, _ = _run_cmd(
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
        repo_root,
    )
    ahead, behind = 0, 0
    if code_sync == 0 and "\t" in sync_info:
        parts = sync_info.split("\t")
        ahead, behind = int(parts[0]), int(parts[1])

    is_clean = len(uncommitted) == 0
    return {
        "status": "pass" if is_clean and behind == 0 else "warn",
        "current_branch": branch,
        "is_clean": is_clean,
        "uncommitted_files_count": len(uncommitted),
        "uncommitted_files": uncommitted[:10],
        "ahead_of_main": ahead,
        "behind_of_main": behind,
    }


def audit_branches(repo_root: Path) -> Dict[str, Any]:
    """Detecta ramas locales y remotas fusionadas o huérfanas, así como worktrees inactivos."""
    # Obtener rama actual activa
    _, cur_branch, _ = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)

    # Ramas locales ya fusionadas en main
    _, merged_out, _ = _run_cmd(["git", "branch", "--merged", "main"], repo_root)
    merged_local = []
    for line in merged_out.splitlines():
        b = line.replace("*", "").replace("+", "").strip()
        if b and b not in ["main", "master", cur_branch]:
            merged_local.append(b)

    # Ramas remotas ya fusionadas en origin/main
    _, rmerged_out, _ = _run_cmd(["git", "branch", "-r", "--merged", "origin/main"], repo_root)
    merged_remote = []
    for line in rmerged_out.splitlines():
        r = line.strip()
        if r.startswith("origin/") and not r.startswith("origin/HEAD") and r != "origin/main":
            merged_remote.append(r.replace("origin/", ""))

    # Worktrees secundarios
    _, wt_out, _ = _run_cmd(["git", "worktree", "list", "--porcelain"], repo_root)
    worktree_count = wt_out.count("worktree ")

    has_stale_branches = len(merged_local) > 0 or len(merged_remote) > 0
    return {
        "status": "warn" if has_stale_branches else "pass",
        "merged_local_branches": merged_local,
        "merged_remote_branches": merged_remote,
        "total_worktrees": worktree_count,
    }


def audit_code_quality(repo_root: Path) -> Dict[str, Any]:
    """Audita el estilo y formato del código Python mediante Ruff."""
    code_lint, lint_out, lint_err = _run_cmd(["ruff", "check", "."], repo_root)
    code_fmt, fmt_out, fmt_err = _run_cmd(["ruff", "format", "--check", "."], repo_root)

    lint_passed = code_lint == 0
    fmt_passed = code_fmt == 0
    return {
        "status": "pass" if (lint_passed and fmt_passed) else "fail",
        "lint_passed": lint_passed,
        "format_passed": fmt_passed,
        "lint_output": lint_out or lint_err,
        "format_output": fmt_out or fmt_err,
    }


def audit_type_checking(repo_root: Path) -> Dict[str, Any]:
    """Audita la integridad de tipos estáticos con Mypy sobre core y api."""
    code, out, err = _run_cmd(["mypy", "core", "api"], repo_root)
    passed = code == 0
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "output": out or err,
    }


def audit_descriptions(repo_root: Path) -> Dict[str, Any]:
    """Verifica la alineación del catálogo canónico de 32 elementos en GitHub."""
    drift_items: List[Dict[str, str]] = []
    for item, canonical in sorted(DESCRIPTIONS_CATALOG.items()):
        actual = get_latest_commit_subject(item)
        if not is_canonical_match(actual, canonical):
            drift_items.append({"item": item, "expected": canonical, "actual": actual})

    synchronized = len(DESCRIPTIONS_CATALOG) - len(drift_items)
    passed = len(drift_items) == 0
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "synchronized_count": synchronized,
        "total_items": len(DESCRIPTIONS_CATALOG),
        "drift_items": drift_items,
    }


def audit_github_workflows(repo_root: Path) -> Dict[str, Any]:
    """Inspecciona los workflows de GitHub Actions para detectar acciones obsoletas o deprecadas."""
    workflows_dir = repo_root / ".github" / "workflows"
    warnings: List[Dict[str, str]] = []

    if workflows_dir.exists():
        for yml_file in workflows_dir.glob("*.y*ml"):
            try:
                content = yml_file.read_text(encoding="utf-8")
                for pat, (suggested, rationale) in DEPRECATED_GITHUB_ACTIONS.items():
                    matches = re.findall(pat, content)
                    if matches:
                        warnings.append(
                            {
                                "file": yml_file.name,
                                "pattern": pat,
                                "suggested": suggested,
                                "reason": rationale,
                            }
                        )
            except Exception as e:
                warnings.append({"file": yml_file.name, "error": f"No se pudo leer archivo: {e}"})

    passed = len(warnings) == 0
    return {
        "status": "pass" if passed else "warn",
        "passed": passed,
        "deprecated_actions": warnings,
    }


def audit_pytest_suite(repo_root: Path, fast: bool = False) -> Dict[str, Any]:
    """Ejecuta la suite de pruebas unitarias automatizadas con Pytest."""
    cmd = ["pytest", "tests/", "-q"] if fast else ["pytest", "tests/", "-v"]
    code, out, err = _run_cmd(cmd, repo_root, timeout=180)
    passed = code == 0
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "exit_code": code,
        "summary": (out.splitlines()[-1] if out else err),
    }


# ==============================================================================
# SECCIÓN 2: CORRECCIÓN Y SANITIZACIÓN (FIX / SANITIZE)
# ==============================================================================


def fix_code_formatting(repo_root: Path) -> bool:
    """Aplica formateo automático en todo el repositorio con Ruff."""
    code, out, _ = _run_cmd(["ruff", "format", "."], repo_root)
    return code == 0


def fix_code_linting(repo_root: Path) -> bool:
    """Aplica autocorrección de linter con Ruff (--fix)."""
    code, out, _ = _run_cmd(["ruff", "check", "--fix", "."], repo_root)
    return code == 0


def fix_descriptions_drift(repo_root: Path) -> bool:
    """Restaura automáticamente descripciones que hayan sufrido desvío."""
    drift = audit_descriptions(repo_root)["drift_items"]
    if not drift:
        return True
    targets = [d["item"] for d in drift]
    res = run_restore(targets)
    return res == 0


def prune_local_merged_branches(repo_root: Path) -> List[str]:
    """Elimina ramas locales que ya estén completamente fusionadas en main."""
    branches_info = audit_branches(repo_root)
    merged = branches_info.get("merged_local_branches", [])
    deleted: List[str] = []

    for b in merged:
        code, _, _ = _run_cmd(["git", "branch", "-d", b], repo_root)
        if code == 0:
            deleted.append(b)
        else:
            # Si fue squasheada en GitHub, intentar borrado forzado seguro si no tiene diff
            diff_code, diff_out, _ = _run_cmd(["git", "diff", f"main..{b}"], repo_root)
            if diff_code == 0 and not diff_out.strip():
                code_force, _, _ = _run_cmd(["git", "branch", "-D", b], repo_root)
                if code_force == 0:
                    deleted.append(b)
    return deleted


def prune_remote_merged_branches(repo_root: Path) -> List[str]:
    """Elimina en el repositorio origin las ramas remotas ya fusionadas en main."""
    branches_info = audit_branches(repo_root)
    merged = branches_info.get("merged_remote_branches", [])
    deleted: List[str] = []

    for b in merged:
        code, _, _ = _run_cmd(["git", "push", "origin", "--delete", b], repo_root)
        if code == 0:
            deleted.append(b)
    return deleted


def prune_git_environment(repo_root: Path) -> Dict[str, Any]:
    """Ejecuta poda de referencias remotas huérfanas y de worktrees."""
    code_fetch, _, _ = _run_cmd(["git", "fetch", "--prune", "origin"], repo_root)
    code_wt, _, _ = _run_cmd(["git", "worktree", "prune"], repo_root)
    return {
        "prune_origin_success": code_fetch == 0,
        "prune_worktrees_success": code_wt == 0,
    }


# ==============================================================================
# SECCIÓN 3: CONTROLADOR Y CLI
# ==============================================================================


def run_full_audit(repo_root: Path, skip_tests: bool = False) -> Dict[str, Any]:
    """Ejecuta una auditoría integral de todos los subsistemas del repositorio."""
    results: Dict[str, Any] = {
        "git_status": audit_git_status(repo_root),
        "branches": audit_branches(repo_root),
        "code_quality": audit_code_quality(repo_root),
        "type_checking": audit_type_checking(repo_root),
        "descriptions": audit_descriptions(repo_root),
        "github_workflows": audit_github_workflows(repo_root),
    }
    if not skip_tests:
        results["pytest_suite"] = audit_pytest_suite(repo_root)

    overall_pass = all(v.get("status") in ["pass", "warn"] for v in results.values() if isinstance(v, dict))
    if not skip_tests and not results["pytest_suite"]["passed"]:
        overall_pass = False

    results["overall_health"] = "HEALTHY" if overall_pass else "ACTION_REQUIRED"
    return results


def print_audit_report(report: Dict[str, Any]) -> None:
    """Imprime el informe de auditoría en consola de manera visual y legible."""
    print("=" * 80)
    print("RTMS - REPORTE GENERAL DE AUDITORIA Y SALUD DEL REPOSITORIO")
    print("=" * 80)

    # Git
    git_st = report["git_status"]
    clean_tag = "[OK]" if git_st["is_clean"] else "[WARN]"
    print(
        f"{clean_tag} Git Status: Rama actual '{git_st['current_branch']}' | "
        f"Limpio: {git_st['is_clean']} | Ahead: {git_st['ahead_of_main']} | Behind: {git_st['behind_of_main']}"
    )
    if git_st["uncommitted_files"]:
        print(f"   Archivos modificados/sin commit ({git_st['uncommitted_files_count']}):")
        for f in git_st["uncommitted_files"]:
            print(f"     * {f}")

    # Branches
    br = report["branches"]
    br_tag = "[OK]" if not br["merged_local_branches"] and not br["merged_remote_branches"] else "[WARN]"
    print(
        f"{br_tag} Ramas: Locales fusionadas: {len(br['merged_local_branches'])} | "
        f"Remotas fusionadas: {len(br['merged_remote_branches'])} | Worktrees: {br['total_worktrees']}"
    )
    if br["merged_local_branches"]:
        print(f"   Ramas locales fusionadas a purgar: {', '.join(br['merged_local_branches'])}")
    if br["merged_remote_branches"]:
        print(f"   Ramas remotas fusionadas en origin: {', '.join(br['merged_remote_branches'])}")

    # Code Quality
    cq = report["code_quality"]
    cq_tag = "[OK]" if cq["status"] == "pass" else "[FAIL]"
    print(
        f"{cq_tag} Calidad de Codigo: Linter Ruff: {'OK' if cq['lint_passed'] else 'FAIL'} | Formateo: {'OK' if cq['format_passed'] else 'FAIL'}"
    )

    # Type Checking
    tc = report["type_checking"]
    tc_tag = "[OK]" if tc["passed"] else "[FAIL]"
    print(f"{tc_tag} Tipado Estatico (Mypy): {'OK' if tc['passed'] else 'FAIL'}")

    # Descriptions
    desc = report["descriptions"]
    desc_tag = "[OK]" if desc["passed"] else "[FAIL]"
    print(
        f"{desc_tag} Descripciones Canonicas GitHub: {desc['synchronized_count']}/{desc['total_items']} sincronizados"
    )
    if desc["drift_items"]:
        print("   Desvios detectados:")
        for d in desc["drift_items"]:
            print(f"     * {d['item']}: esperado='{d['expected']}' | actual='{d['actual']}'")

    # GitHub Actions
    gh = report["github_workflows"]
    gh_tag = "[OK]" if gh["passed"] else "[WARN]"
    dep_count = len(gh.get("deprecated_actions", []))
    gh_msg = "Sin acciones obsoletas" if gh["passed"] else f"{dep_count} advertencias"
    print(f"{gh_tag} Workflows GitHub Actions: {gh_msg}")
    if gh["deprecated_actions"]:
        for item in gh["deprecated_actions"]:
            print(f"     * {item['file']}: {item['suggested']} ({item['reason']})")

    # Pytest
    if "pytest_suite" in report:
        py_st = report["pytest_suite"]
        py_tag = "[OK]" if py_st["passed"] else "[FAIL]"
        print(f"{py_tag} Suite de Pruebas Automatizadas (Pytest): {'OK' if py_st['passed'] else 'FAIL'}")
        if py_st.get("summary"):
            print(f"   {py_st['summary']}")

    print("=" * 80)
    print(f"ESTADO GENERAL: {report['overall_health']}")
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Herramienta integral de auditoría, corrección y sanitización del repositorio RTMS."
    )
    parser.add_argument("--audit", "--check", action="store_true", help="Audita el estado general del repositorio.")
    parser.add_argument(
        "--fix", action="store_true", help="Aplica correcciones automáticas de formato, linter y descripciones."
    )
    parser.add_argument(
        "--prune-local", action="store_true", help="Elimina ramas locales que ya están fusionadas en main."
    )
    parser.add_argument(
        "--prune-remote", action="store_true", help="Elimina ramas remotas en origin fusionadas en main."
    )
    parser.add_argument(
        "--prune-env", action="store_true", help="Poda referencias remotas huérfanas y worktrees inactivos."
    )
    parser.add_argument("--test", action="store_true", help="Ejecuta la suite de pruebas unitarias.")
    parser.add_argument(
        "--full", action="store_true", help="Ejecuta auditoría, autocorrección, poda de ramas y pruebas."
    )
    parser.add_argument("--json", action="store_true", help="Imprime el resultado en formato JSON para CI/CD.")

    args = parser.parse_args()
    repo_root = get_repo_root()

    # Si no se pasó ningún argumento, ejecutar auditoría por defecto
    if not (
        args.audit or args.fix or args.prune_local or args.prune_remote or args.prune_env or args.test or args.full
    ):
        args.audit = True

    fix_applied = False
    pruned_local: List[str] = []
    pruned_remote: List[str] = []

    if args.full or args.fix:
        print("Aplicando correcciones automáticas de código y descripciones...")
        f1 = fix_code_formatting(repo_root)
        f2 = fix_code_linting(repo_root)
        f3 = fix_descriptions_drift(repo_root)
        fix_applied = f1 and f2 and f3
        print(
            f"Formateo: {'OK' if f1 else 'FAIL'} | Linter fix: {'OK' if f2 else 'FAIL'} | Descripciones: {'OK' if f3 else 'FAIL'}"
        )

    if args.full or args.prune_local:
        pruned_local = prune_local_merged_branches(repo_root)
        if pruned_local:
            print(f"Ramas locales eliminadas: {', '.join(pruned_local)}")

    if args.full or args.prune_remote:
        pruned_remote = prune_remote_merged_branches(repo_root)
        if pruned_remote:
            print(f"Ramas remotas en origin eliminadas: {', '.join(pruned_remote)}")

    if args.full or args.prune_env:
        prune_git_environment(repo_root)
        print("Poda de referencias remotas y worktrees completada.")

    # Ejecutar reporte de auditoría
    report = run_full_audit(repo_root, skip_tests=not (args.full or args.test))
    report["fix_applied"] = fix_applied
    report["pruned_local_branches"] = pruned_local
    report["pruned_remote_branches"] = pruned_remote

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_audit_report(report)

    return 0 if report["overall_health"] == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
