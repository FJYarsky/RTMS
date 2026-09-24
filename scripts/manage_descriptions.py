# ==============================================================================
# RTMS — Real-Time Multicam System
# Gestión, auditoría y preservación de descripciones de archivos en GitHub.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Gestión, auditoría y preservación de descripciones canónicas en GitHub."""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Catálogo canónico de descripciones para los 31 elementos raíz en GitHub.
# Longitud estrictamente menor a 45 caracteres para evitar truncamientos con '...'.
DESCRIPTIONS_CATALOG: Dict[str, str] = {
    ".github": "ci: pipelines de integracion y release",
    ".gitignore": "chore: reglas de exclusion de git",
    ".pre-commit-config.yaml": "ci: hooks de pre-commit para linters",
    "api": "api: endpoints REST y validacion",
    "build_portable.bat": "build: empaquetador portable Windows",
    "CHANGELOG.md": "docs: historial de cambios del sistema",
    "CODE_OF_CONDUCT.md": "docs: codigo de conducta de la comunidad",
    "config": "config: plantilla de configuracion",
    "conftest.py": "tests: configuracion y fixtures globales",
    "CONTRIBUTING.md": "docs: guia de contribucion al proyecto",
    "core": "core: motor de transmision y telemetria",
    "docs": "docs: manuales tecnicos y guias",
    "gui": "gui: interfaz web y panel de control",
    "icon.ico": "assets: icono de aplicacion y bandeja",
    "justfile": "tools: recetas de automatizacion y build",
    "LATEST_RELEASE.md": "docs: notas de la version mas reciente",
    "LICENSE": "legal: terminos de la licencia MIT",
    "main.py": "app: punto de entrada y servidor principal",
    "pyproject.toml": "build: configuracion y metadatos",
    "README.md": "docs: guia general del sistema y uso",
    "RELEASE_NOTES.md": "docs: notas oficiales de lanzamiento",
    "requirements-dev.txt": "deps: dependencias de desarrollo y test",
    "requirements-lock.txt": "deps: versiones fijadas para despliegue",
    "requirements.txt": "deps: dependencias de produccion",
    "rtms.exe.config": "config: manifiesto de ejecucion CLR .NET",
    "run.bat": "tools: lanzador rapido para Windows",
    "scripts": "scripts: utilidades de arranque y test",
    "SECURITY.md": "docs: politica de reporte de seguridad",
    "site": "web: sitio oficial y portal de descargas",
    "tests": "tests: suite de pruebas automatizadas",
    "THIRD_PARTY_NOTICES.md": "legal: licencias de librerias de terceros",
    "uv.lock": "deps: resolucion determinista de paquetes",
}


def get_repo_root() -> Path:
    """Obtiene la ruta raíz del repositorio de Git."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return Path(out)
    except Exception:
        # Fallback a directorio padre de scripts/
        return Path(__file__).resolve().parent.parent


def is_shallow_repo() -> bool:
    """Verifica si el repositorio local es un clon superficial (shallow clone)."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--is-shallow-repository"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out.lower() == "true"
    except Exception:
        return False


def get_latest_commit_subject(item_path: str) -> str:
    """Obtiene el asunto del último commit que modificó la ruta especificada."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-n", "1", "--format=%s", "--", item_path],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out
    except Exception:
        return ""


def is_canonical_match(actual: str, canonical: str) -> bool:
    """Verifica si el asunto coincide con el catálogo canónico, tolerando sufijos de PR (#123)."""
    if actual == canonical:
        return True
    # Tolerar sufijo de merge de Pull Request de GitHub (#123)
    if re.sub(r"\s*\(\#\d+\)$", "", actual) == canonical:
        return True
    return False


def run_list() -> None:
    """Imprime el catálogo canónico de elementos y descripciones."""
    print("=" * 80)
    print("CATÁLOGO CANÓNICO DE DESCRIPCIONES EN GITHUB (RTMS)")
    print("=" * 80)
    print(f"{'Elemento':<24} | {'Long':<4} | {'Descripción Canónica'}")
    print("-" * 80)
    for item, desc in sorted(DESCRIPTIONS_CATALOG.items()):
        print(f"{item:<24} | {len(desc):<4} | {desc}")
    print("=" * 80)
    print(f"Total de elementos catalogados: {len(DESCRIPTIONS_CATALOG)}")


def run_check() -> int:
    """Audita el repositorio comparando el último commit de cada ruta con el catálogo."""
    print("Iniciando auditoría de descripciones en GitHub...")
    drift_items: List[Tuple[str, str, str]] = []
    matched_count = 0

    for item, canonical in sorted(DESCRIPTIONS_CATALOG.items()):
        actual = get_latest_commit_subject(item)
        if is_canonical_match(actual, canonical):
            matched_count += 1
        else:
            drift_items.append((item, canonical, actual))

    print(f"Sincronizados: {matched_count}/{len(DESCRIPTIONS_CATALOG)}")

    if drift_items:
        print("\n[ALERTA] Se detectaron desvíos (drift) en las descripciones:")
        print("-" * 80)
        for item, canonical, actual in drift_items:
            print(f"• Elemento:   {item}")
            print(f"  Esperado:   '{canonical}'")
            print(f"  Actual:     '{actual}'")
            print("-" * 80)
        if is_shallow_repo():
            print(
                "\n[NOTA] El repositorio es un clon superficial (shallow clone); ejecute 'git fetch --unshallow' para cargar el historial completo."
            )
        print("\nPara corregirlos ejecuta: python scripts/manage_descriptions.py --restore")
        return 1

    print("[OK] Todos los elementos están perfectamente alineados con el catálogo oficial.")
    return 0


def run_commit_helper(target_file: str, body_message: str) -> int:
    """Ayudante de commits bajo la Convención Asunto/Cuerpo (Opción 1)."""
    norm_path = target_file.replace("\\", "/").strip()
    root_item = norm_path.split("/")[0]

    subject = DESCRIPTIONS_CATALOG.get(norm_path) or DESCRIPTIONS_CATALOG.get(root_item)
    if not subject:
        # Si no está en catálogo exacto, inferir por tipo
        if norm_path.endswith(".py"):
            subject = "app: actualizacion de logica interna"
        else:
            subject = "chore: actualizacion de archivos del repositorio"

    print(f"Preparando commit para: {target_file}")
    print(f"Asunto (GitHub):        {subject}")
    print(f"Cuerpo (Detalle):       {body_message}")

    try:
        subprocess.run(["git", "add", target_file], check=True)
        cmd = ["git", "commit", "-m", subject]
        if body_message:
            cmd.extend(["-m", body_message])
        subprocess.run(cmd, check=True)
        print("[OK] Commit creado con éxito cumpliendo la convención Asunto/Cuerpo.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Falló la creación del commit: {e}", file=sys.stderr)
        return 1


def _touch_file_cleanly(file_path: Path) -> bool:
    """Aplica una modificación neutra para registrar un commit limpio."""
    if not file_path.exists():
        return False

    suffix = file_path.suffix.lower()
    try:
        if suffix in [
            ".py",
            ".md",
            ".yml",
            ".yaml",
            ".json",
            ".txt",
            ".bat",
            ".vbs",
            ".config",
            ".html",
            ".js",
            ".css",
            ".ps1",
            ".toml",
        ] or file_path.name == "justfile":
            content = file_path.read_text(encoding="utf-8")
            # Alternar salto neutro al final para asegurar que git detecte un diff real
            if content.endswith("\n\n"):
                normalized = content.rstrip("\r\n") + "\n"
            else:
                normalized = content.rstrip("\r\n") + "\n\n"
            file_path.write_text(normalized, encoding="utf-8", newline="\n")
            return True
        elif file_path.name == "icon.ico":
            # Para icon.ico, verificar que exista y sea legible
            data = file_path.read_bytes()
            file_path.write_bytes(data)
            return True
        return False
    except Exception as e:
        print(f"Error tocando {file_path}: {e}", file=sys.stderr)
        return False


def run_restore(targets: List[str]) -> int:
    """Restaura las descripciones de los elementos especificados o con desvío."""
    repo_root = get_repo_root()
    items_to_restore = targets if targets else []

    if not items_to_restore:
        # Detectar cuáles están desincronizados
        for item, canonical in DESCRIPTIONS_CATALOG.items():
            actual = get_latest_commit_subject(item)
            if not is_canonical_match(actual, canonical):
                items_to_restore.append(item)

    if not items_to_restore:
        print("[OK] No hay elementos que requieran restauración.")
        return 0

    print(f"Restaurando {len(items_to_restore)} elemento(s)...")
    success_count = 0

    for item in items_to_restore:
        canonical = DESCRIPTIONS_CATALOG.get(item)
        if not canonical:
            print(f"[SKIP] Elemento '{item}' no está en el catálogo.")
            continue

        item_path = repo_root / item
        touched = False

        if item_path.is_dir():
            # Buscar archivo representativo dentro del directorio
            for child in item_path.rglob("*"):
                if child.is_file() and child.suffix.lower() in [
                    ".py",
                    ".md",
                    ".yml",
                    ".js",
                    ".css",
                    ".html",
                    ".json",
                    ".ps1",
                ]:
                    _touch_file_cleanly(child)
                    subprocess.run(["git", "add", str(child)], check=False)
                    touched = True
                    break
        elif item_path.is_file():
            touched = _touch_file_cleanly(item_path)
            subprocess.run(["git", "add", str(item_path)], check=False)

        if touched:
            msg_body = "Mantenimiento automatizado: preservación de descripción canónica en GitHub."
            res = subprocess.run(
                ["git", "commit", "-m", canonical, "-m", msg_body],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                print(f"[RESTORED] {item} -> '{canonical}'")
                success_count += 1
            else:
                # Si git no detectó cambios reales, forzar commit vacío de metadata
                res_empty = subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", canonical, "-m", msg_body],
                    capture_output=True,
                    text=True,
                )
                if res_empty.returncode == 0:
                    print(f"[RESTORED (meta)] {item} -> '{canonical}'")
                    success_count += 1
                else:
                    print(f"[ERROR] No se pudo restaurar {item}: {res.stderr.strip()}", file=sys.stderr)

    print(f"\nRestauración completada: {success_count}/{len(items_to_restore)} elementos.")
    return 0 if success_count == len(items_to_restore) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gestión y preservación de descripciones de archivos en GitHub (RTMS)."
    )
    parser.add_argument("--list", action="store_true", help="Muestra el catálogo canónico completo.")
    parser.add_argument("--check", action="store_true", help="Audita el estado actual y detecta desvíos.")
    parser.add_argument("--restore", nargs="*", metavar="ITEM", help="Restaura la descripción de los elementos.")
    parser.add_argument("--commit", metavar="FILE", help="Archivo a comitear bajo convención Asunto/Cuerpo.")
    parser.add_argument("-m", "--message", default="", help="Cuerpo o detalle técnico del commit.")

    args = parser.parse_args()

    if args.list:
        run_list()
        return 0
    elif args.check:
        return run_check()
    elif args.restore is not None:
        return run_restore(args.restore)
    elif args.commit:
        return run_commit_helper(args.commit, args.message)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
