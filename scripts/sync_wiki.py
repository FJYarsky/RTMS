# ==============================================================================
# RTMS — Real-Time Multicam System
# Sincronización, compilación y despliegue automatizado de la GitHub Wiki.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Herramienta de compilación, validación y sincronización de la GitHub Wiki de RTMS."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOCS_DIR = _REPO_ROOT / "docs"
_WIKI_SRC_DIR = _REPO_ROOT / "docs" / "wiki"
_BUILD_DIR = _REPO_ROOT / "build" / "wiki"


_STOP_WORDS: Set[str] = {"de", "del", "y", "e", "en", "el", "la", "los", "las", "por", "con", "a", "al"}


def _format_word(w: str, idx: int) -> str:
    """Aplica formato capitalizado respetando palabras de enlace en español."""
    w_lower = w.lower()
    if w_lower in _STOP_WORDS and idx > 0:
        return w_lower
    if w_lower == "e2e":
        return "E2e"
    return w.capitalize()


def get_wiki_slug(filename: str) -> str:
    """Convierte un nombre de archivo en un slug canónico de GitHub Wiki."""
    stem = Path(filename).stem
    # Si es un ADR tipo 0001-algo -> ADR-0001-Algo
    if re.match(r"^\d{4}-", stem):
        parts = stem.split("-", 1)
        num = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        words = [_format_word(w, i) for i, w in enumerate(rest.split("-"))]
        return f"ADR-{num}-{'-'.join(words)}"

    # Si es un RFC tipo RFC-0001-algo -> RFC-0001-Algo
    if re.match(r"^RFC-\d{4}-", stem, re.IGNORECASE):
        parts = stem.split("-", 2)
        prefix = parts[0].upper()
        num = parts[1]
        rest = parts[2] if len(parts) > 2 else ""
        words = [_format_word(w, i) for i, w in enumerate(rest.split("-"))]
        return f"{prefix}-{num}-{'-'.join(words)}"

    # Caso general
    words = [_format_word(w, i) for i, w in enumerate(stem.replace("_", "-").split("-"))]
    return "-".join(words)


def sanitize_markdown_for_wiki(content: str, current_slug: str) -> str:
    """Adapta enlaces relativos locales y rutas de archivos para su visualización en GitHub Wiki."""
    # Reemplazar enlaces locales de tipo [algo](file:///...) por enlaces limpios de código
    content = re.sub(r"\[([^\]]+)\]\(file:///[^\)]+\)", r"`\1`", content)

    # Reemplazar enlaces a ADRs relativos: adr/0010-...md, ../adr/0010-...md o 0010-...md
    def replace_adr_link(match: re.Match) -> str:
        text = match.group(1)
        filename = match.group(2)
        slug = get_wiki_slug(filename)
        return f"[{text}]({slug})"

    content = re.sub(r"\[([^\]]+)\]\((?:(?:\.\./)?adr/)?(\d{4}-[^)]+\.md)\)", replace_adr_link, content)
    content = re.sub(r"\[([^\]]+)\]\((?:(?:\.\./)?rfc/)?(RFC-\d{4}-[^)]+\.md)\)", replace_adr_link, content)

    # Reemplazar enlaces a arquitectura: ../architecture/c4-system-architecture.md -> Arquitectura-del-Sistema
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?architecture/c4-system-architecture\.md\)",
        r"[\1](Arquitectura-del-Sistema)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?architecture/concurrency-threading-model\.md\)",
        r"[\1](Modelo-de-Concurrencia-e-Hilos)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?architecture/interface-contracts-and-protocols\.md\)",
        r"[\1](Contratos-de-Interfaz-y-Protocolos)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?ops/runbook-and-operations-guide\.md\)",
        r"[\1](Runbook-y-Operaciones)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?TRACEABILITY_MATRIX\.md\)",
        r"[\1](Matriz-de-Trazabilidad)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?HARDWARE\.md\)",
        r"[\1](Compatibilidad-de-Hardware)",
        content,
    )
    content = re.sub(
        r"\[([^\]]+)\]\((?:\.\./)?TROUBLESHOOTING\.md\)",
        r"[\1](Diagnostico-y-Resolucion-de-Incidentes)",
        content,
    )

    return content


def sync_docs_to_wiki_sources() -> int:
    """Sincroniza y adapta documentos desde docs/ hacia docs/wiki/."""
    _WIKI_SRC_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    # 1. Copiar y adaptar ADRs
    adr_dir = _DOCS_DIR / "adr"
    if adr_dir.exists():
        for adr_file in sorted(adr_dir.glob("*.md")):
            if adr_file.name in ["README.md", "template.md"]:
                continue
            slug = get_wiki_slug(adr_file.name)
            target = _WIKI_SRC_DIR / f"{slug}.md"
            content = adr_file.read_text(encoding="utf-8")
            adapted = sanitize_markdown_for_wiki(content, slug)
            target.write_text(adapted, encoding="utf-8", newline="\n")
            count += 1

    # 2. Copiar y adaptar RFCs
    rfc_dir = _DOCS_DIR / "rfc"
    if rfc_dir.exists():
        for rfc_file in sorted(rfc_dir.glob("RFC-*.md")):
            if rfc_file.name in ["README.md", "template.md"]:
                continue
            slug = get_wiki_slug(rfc_file.name)
            target = _WIKI_SRC_DIR / f"{slug}.md"
            content = rfc_file.read_text(encoding="utf-8")
            adapted = sanitize_markdown_for_wiki(content, slug)
            target.write_text(adapted, encoding="utf-8", newline="\n")
            count += 1

    # 3. Documentos estructurales de Arquitectura y Operaciones
    mappings = {
        _DOCS_DIR / "architecture" / "c4-system-architecture.md": "Arquitectura-del-Sistema.md",
        _DOCS_DIR / "architecture" / "concurrency-threading-model.md": "Modelo-de-Concurrencia-e-Hilos.md",
        _DOCS_DIR / "architecture" / "interface-contracts-and-protocols.md": "Contratos-de-Interfaz-y-Protocolos.md",
        _DOCS_DIR / "ops" / "runbook-and-operations-guide.md": "Runbook-y-Operaciones.md",
        _DOCS_DIR / "TRACEABILITY_MATRIX.md": "Matriz-de-Trazabilidad.md",
        _DOCS_DIR / "HARDWARE.md": "Compatibilidad-de-Hardware.md",
        _DOCS_DIR / "TROUBLESHOOTING.md": "Diagnostico-y-Resolucion-de-Incidentes.md",
    }

    for src_path, target_name in mappings.items():
        if src_path.exists():
            target = _WIKI_SRC_DIR / target_name
            slug = Path(target_name).stem
            content = src_path.read_text(encoding="utf-8")
            adapted = sanitize_markdown_for_wiki(content, slug)
            target.write_text(adapted, encoding="utf-8", newline="\n")
            count += 1

    return count


def build_wiki_distribution(dest_dir: Path = _BUILD_DIR) -> List[Path]:
    """Compila y ensambla la totalidad de las páginas de la wiki en un directorio plano listo para git push."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Asegurar sincronización previa
    sync_docs_to_wiki_sources()

    # 2. Copiar todos los archivos .md de docs/wiki/ al directorio de build
    compiled_files: List[Path] = []
    for md_file in _WIKI_SRC_DIR.glob("*.md"):
        target = dest_dir / md_file.name
        content = md_file.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8", newline="\n")
        compiled_files.append(target)

    return compiled_files


def validate_wiki_integrity(wiki_dir: Path = _WIKI_SRC_DIR) -> Tuple[bool, List[str], List[str]]:
    """Valida la presencia de archivos esenciales y que no existan enlaces rotos en la wiki."""
    errors: List[str] = []
    warnings: List[str] = []

    # Verificar existencia de archivos obligatorios
    mandatory = ["Home.md", "_Sidebar.md", "_Footer.md"]
    for m in mandatory:
        if not (wiki_dir / m).exists():
            errors.append(f"Archivo obligatorio ausente: '{m}'")

    # Mapeo de todas las páginas disponibles (normalizado en minúsculas)
    existing_pages: Set[str] = {p.stem.lower() for p in wiki_dir.glob("*.md")}

    # Validar enlaces dentro de _Sidebar.md y cada página
    for md_file in wiki_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")

        # 1. Enlaces estilo wiki: [[Display|Target]] o [[Target]]
        wiki_links = re.findall(r"\[\[([^\]]+)\]\]", content)
        for link in wiki_links:
            target = link.split("|")[-1].strip()
            # Ignorar anclas #
            target_page = target.split("#")[0]
            if target_page and target_page.lower() not in existing_pages:
                errors.append(f"Enlace wiki roto en '{md_file.name}': [[{link}]] -> '{target_page}' no existe")

        # 2. Enlaces markdown relativos: [Texto](Pagina) sin esquema http/https ni anclas puras
        md_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        for text, url in md_links:
            url_clean = url.strip()
            if (
                url_clean.startswith("http://")
                or url_clean.startswith("https://")
                or url_clean.startswith("mailto:")
                or url_clean.startswith("#")
            ):
                continue
            # Quitar anclas
            page_slug = url_clean.split("#")[0]
            page_slug = Path(page_slug).stem
            if page_slug and page_slug.lower() not in existing_pages:
                warnings.append(f"Posible enlace roto en '{md_file.name}': [{text}]({url_clean})")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def deploy_wiki(
    wiki_repo_url: str = "https://github.com/FJYarsky/RTMS.wiki.git",
    build_dir: Path = _BUILD_DIR,
    token: str = None,
) -> int:
    """Clona el repositorio de la wiki de GitHub, copia los archivos compilados y hace push."""
    print("Iniciando despliegue de la GitHub Wiki...")

    # Compilar primero
    files = build_wiki_distribution(build_dir)
    print(f"Páginas compiladas para despliegue: {len(files)}")

    # Validar integridad
    valid, errors, warnings = validate_wiki_integrity(build_dir)
    if not valid:
        print("[ERROR] Falló la validación de integridad de la wiki:")
        for err in errors:
            print(f"  * {err}")
        return 1

    temp_clone_dir = _REPO_ROOT / "build" / "wiki_clone"
    if temp_clone_dir.exists():
        shutil.rmtree(temp_clone_dir)

    target_url = wiki_repo_url
    if token:
        # Inyectar token en la URL de autenticación
        if "github.com/" in target_url:
            target_url = target_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")

    print(f"Comprobando disponibilidad de: {wiki_repo_url}")
    # Comprobar si el repositorio de la wiki existe / está inicializado
    check_cmd = ["git", "ls-remote", target_url]
    res_check = subprocess.run(check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if res_check.returncode != 0:
        print("\n" + "=" * 80)
        print("[AVISO IMPORTANTE: WIKI DE GITHUB NO INICIALIZADA]")
        print("=" * 80)
        print("GitHub requiere que la Wiki sea activada en la interfaz web antes de permitir")
        print("el acceso vía Git (retorna 'repository not found').")
        print("\nPasos para activarla en 30 segundos:")
        print("1. Abre en tu navegador: https://github.com/FJYarsky/RTMS/wiki")
        print("2. Haz clic en el botón verde 'Create the first page' o 'Set up your first page'.")
        print("3. Guarda la página (puedes dejar cualquier título o 'Home').")
        print("4. Vuelve a ejecutar 'just wiki-deploy' o activa el workflow de GitHub Actions.")
        print("=" * 80 + "\n")
        return 2

    # Clonar repositorio existente
    clone_cmd = ["git", "clone", target_url, str(temp_clone_dir)]
    res_clone = subprocess.run(clone_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_clone.returncode != 0:
        print(f"[ERROR] No se pudo clonar el repositorio wiki: {res_clone.stderr}")
        return 1

    # Copiar todos los archivos de build al clon
    for f in build_dir.glob("*.md"):
        shutil.copy2(f, temp_clone_dir / f.name)

    # Configurar committer e inspeccionar status
    subprocess.run(["git", "config", "user.name", "RTMS Bot / Joaquin Yarsky"], cwd=temp_clone_dir, check=True)
    subprocess.run(["git", "config", "user.email", "joaquinyarsky@gmail.com"], cwd=temp_clone_dir, check=True)

    subprocess.run(["git", "add", "."], cwd=temp_clone_dir, check=True)
    diff_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=temp_clone_dir, stdout=subprocess.PIPE, text=True
    )

    if not diff_status.stdout.strip():
        print("[OK] La Wiki ya se encuentra completamente sincronizada con los últimos cambios.")
        shutil.rmtree(temp_clone_dir, ignore_errors=True)
        return 0

    # Crear commit
    commit_cmd = ["git", "commit", "-m", "docs(wiki): sincronizar documentacion del sistema RTMS"]
    subprocess.run(commit_cmd, cwd=temp_clone_dir, check=True)

    # Push
    push_cmd = ["git", "push", "origin", "master"]
    res_push = subprocess.run(push_cmd, cwd=temp_clone_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_push.returncode != 0:
        # Algunos wikis usan main
        push_cmd_main = ["git", "push", "origin", "main"]
        res_push = subprocess.run(
            push_cmd_main, cwd=temp_clone_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

    if res_push.returncode != 0:
        print(f"[ERROR] Falló el push al repositorio wiki: {res_push.stderr}")
        return 1

    print("[EXITO] Wiki de GitHub actualizada y publicada exitosamente.")
    shutil.rmtree(temp_clone_dir, ignore_errors=True)
    return 0


def main() -> int:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Gestión y sincronización de la GitHub Wiki de RTMS.")
    parser.add_argument("--build", action="store_true", help="Compila la wiki a build/wiki.")
    parser.add_argument("--check", action="store_true", help="Valida la integridad de enlaces y archivos.")
    parser.add_argument("--sync-docs", action="store_true", help="Sincroniza documentos desde docs/ hacia docs/wiki/.")
    parser.add_argument("--deploy", action="store_true", help="Despliega la wiki al repositorio remoto de GitHub.")
    parser.add_argument("--token", type=str, default=os.environ.get("GITHUB_TOKEN"), help="Token de autenticación.")
    parser.add_argument(
        "--repo-url",
        type=str,
        default="https://github.com/FJYarsky/RTMS.wiki.git",
        help="URL del repositorio wiki.",
    )

    args = parser.parse_args()

    if not (args.build or args.check or args.sync_docs or args.deploy):
        # Acción por defecto: sync y check
        args.sync_docs = True
        args.check = True

    if args.sync_docs:
        count = sync_docs_to_wiki_sources()
        print(f"Documentos sincronizados hacia docs/wiki/: {count}")

    if args.build:
        files = build_wiki_distribution()
        print(f"Compilación completada: {len(files)} páginas ensambladas en {Path('build/wiki').as_posix()}")

    if args.check:
        target = _BUILD_DIR if _BUILD_DIR.exists() else _WIKI_SRC_DIR
        valid, errors, warnings = validate_wiki_integrity(target)
        print(f"Validando integridad en: {target.as_posix()}...")
        for w in warnings:
            print(f"  [AVISO] {w}")
        if not valid:
            print(f"[ERROR] Se detectaron {len(errors)} errores de integridad:")
            for e in errors:
                print(f"  * {e}")
            return 1
        print("[OK] Integridad de la Wiki verificada al 100% sin enlaces rotos.")

    if args.deploy:
        return deploy_wiki(wiki_repo_url=args.repo_url, token=args.token)

    return 0


if __name__ == "__main__":
    sys.exit(main())
