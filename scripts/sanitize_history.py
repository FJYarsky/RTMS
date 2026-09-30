#!/usr/bin/env python3
# ==============================================================================
# RTMS — Real-Time Multicam System
# Script de auditoría y sanitización retroactiva de datos personales en Git.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Herramienta de auditoría y redacción retroactiva de información personal en el historial Git.
Permite identificar y generar las reglas de reemplazo para purgar números de teléfono,
enlaces de WhatsApp y datos de contacto legados de todo el historial de commits y tags de RTMS.

Canales oficiales únicos autorizados:
- Correo electrónico: joaquinyarsky@gmail.com
- Perfil y repositorio GitHub: https://github.com/FJYarsky / https://github.com/FJYarsky/RTMS
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Patrones sensibles a detectar en el historial
SENSITIVE_PATTERNS = [
    "437980",
    "5492625",
    "+54 2625",
    "wa.me",
    "btn-whatsapp",
]

# Reglas de sustitución para git-filter-repo: texto_original==>texto_reemplazo
REPLACEMENT_RULES: List[Tuple[str, str]] = [
    (
        "* 💬 WhatsApp: [+54 2625-437980](https://wa.me/5492625437980)",
        "* 📧 Email: [joaquinyarsky@gmail.com](mailto:joaquinyarsky@gmail.com)",
    ),
    ("https://wa.me/5492625437980", "https://github.com/FJYarsky"),
    ("https://wa.me/+5492625437980", "https://github.com/FJYarsky"),
    ("+54 2625-437980", "joaquinyarsky@gmail.com"),
    ("+54 9 2625-437980", "joaquinyarsky@gmail.com"),
    ("5492625437980", "joaquinyarsky"),
    (".btn-whatsapp", ".btn-contact-official"),
]


def run_cmd(cmd: List[str], cwd: Path = REPO_ROOT) -> Tuple[int, str, str]:
    """Ejecuta un comando en consola capturando su salida."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def scan_git_history() -> Dict[str, List[Dict[str, str]]]:
    """Escanea el historial de Git en busca de cadenas sensibles."""
    findings: Dict[str, List[Dict[str, str]]] = {}

    for pattern in SENSITIVE_PATTERNS:
        code, out, _ = run_cmd(["git", "log", f"-S{pattern}", "--format=%h|%an|%ad|%s", "--date=short"])
        if code == 0 and out:
            pattern_commits = []
            for line in out.splitlines():
                parts = line.split("|", 3)
                if len(parts) == 4:
                    pattern_commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "subject": parts[3],
                        }
                    )
            if pattern_commits:
                findings[pattern] = pattern_commits

    return findings


def print_scan_report(findings: Dict[str, List[Dict[str, str]]]) -> None:
    """Imprime en consola los resultados del escaneo histórico."""
    print("=" * 80)
    print("RTMS — AUDITORÍA RETROACTIVA DE PRIVACIDAD EN HISTORIAL GIT")
    print("=" * 80)

    if not findings:
        print("[OK] No se detectaron cadenas sensibles en el historial analizado.")
        return

    total_occurrences = sum(len(v) for v in findings.values())
    print(f"[ALERTA] Se detectaron {total_occurrences} referencias históricas con datos personales:\n")

    seen_hashes = set()
    for pattern, commits in findings.items():
        print(f"Patrón detectado: '{pattern}' ({len(commits)} commits)")
        for c in commits:
            seen_hashes.add(c["hash"])
            print(f"  - [{c['hash']}] {c['date']} | {c['author']}: {c['subject']}")
        print()

    print(f"Total de commits únicos afectados: {len(seen_hashes)}")
    print("Canales oficiales autorizados: joaquinyarsky@gmail.com | https://github.com/FJYarsky")
    print("=" * 80)


def generate_replacement_file(output_path: Path) -> Path:
    """Genera el archivo de sustituciones estándar para git-filter-repo."""
    lines = []
    for orig, repl in REPLACEMENT_RULES:
        lines.append(f"{orig}==>{repl}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def print_filter_guide(rules_path: Path) -> None:
    """Imprime la guía paso a paso para ejecutar la reescritura de historial de forma segura."""
    guide = f"""
================================================================================
GUÍA OFICIAL: REESCRITURA Y SANITIZACIÓN RETROACTIVA DEL HISTORIAL DE GIT
================================================================================

ADVERTENCIA:
Reescribir el historial de Git cambia los hashes SHA-1 de los commits afectados
y requiere un 'git push --force' hacia el repositorio remoto.

PASO 1: CREAR UN BACKUP LOCAL COMPLETO (CLON EN ESPEJO)
--------------------------------------------------------------------------------
Antes de cualquier modificación destructiva, clona un respaldo espejo fuera del worktree:
  cd ..
  git clone --mirror https://github.com/FJYarsky/RTMS.git RTMS_backup_mirror.git

PASO 2: INSTALAR GIT-FILTER-REPO (HERRAMIENTA OFICIAL RECOMENDADA POR GIT)
--------------------------------------------------------------------------------
La herramienta oficial y segura para reescribir historial es git-filter-repo:
  pip install git-filter-repo

PASO 3: GENERAR EL ARCHIVO DE REEMPLAZO DE DATOS SENSIBLES
--------------------------------------------------------------------------------
Se ha generado el archivo de reglas en:
  {rules_path.resolve()}

Contiene los mapeos exactos para sustituir números telefónicos y enlaces de WhatsApp
por los canales oficiales (joaquinyarsky@gmail.com y github.com/FJYarsky).

PASO 4: EJECUTAR LA PURGA EN UN CLON LIMPIO DEL REPOSITORIO
--------------------------------------------------------------------------------
En una copia limpia recién clonada de RTMS:
  git filter-repo --replace-text {rules_path.name} --force

PASO 5: VERIFICAR LA ELIMINACIÓN DE LOS DATOS SENSIBLES
--------------------------------------------------------------------------------
Verifica que ninguna búsqueda por los números legados devuelva resultados:
  git log -S "437980" --oneline
  git log -S "5492625" --oneline
  git log -S "wa.me" --oneline

Ambos comandos deben finalizar sin imprimir ninguna línea.

PASO 6: FORZAR LA ACTUALIZACIÓN EN GITHUB (SOLO EL ADMINISTRADOR / PROPIETARIO)
--------------------------------------------------------------------------------
Restablece el remoto si git-filter-repo lo desconectó:
  git remote add origin https://github.com/FJYarsky/RTMS.git

Fuerza la subida de todas las ramas y tags saneados:
  git push origin --force --all
  git push origin --force --tags

PASO 7: PURGA DE VISTAS EN CACHÉ DE GITHUB
--------------------------------------------------------------------------------
GitHub mantiene en caché commits huérfanos durante unos días si fueron visualizados
o referenciados en pull requests pasados. Si se requiere purga inmediata de la caché
del lado del servidor, contacta a GitHub Support indicando que se ha saneado
información de privacidad en el repositorio.
================================================================================
"""
    print(guide)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auditoría y saneamiento retroactivo de datos personales en el historial de Git."
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Escanear historial de Git y listar commits que contienen datos sensibles.",
    )
    parser.add_argument(
        "--generate-rules",
        action="store_true",
        help="Generar el archivo 'scripts/git_replace_expressions.txt' para git-filter-repo.",
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Mostrar guía completa paso a paso para ejecutar git-filter-repo de forma segura.",
    )

    args = parser.parse_args()

    # Si no se pasa ningún argumento, ejecutar scan y mostrar resumen con guía
    if not (args.scan or args.generate_rules or args.guide):
        args.scan = True
        args.generate_rules = True
        args.guide = True

    rules_file = REPO_ROOT / "scripts" / "git_replace_expressions.txt"

    if args.scan:
        findings = scan_git_history()
        print_scan_report(findings)

    if args.generate_rules:
        generate_replacement_file(rules_file)
        print(f"[OK] Archivo de reglas de sustitución generado en: {rules_file}")

    if args.guide:
        print_filter_guide(rules_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
