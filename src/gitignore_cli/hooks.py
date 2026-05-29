from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gitignore_cli.deps import ensure_detection_tools
from gitignore_cli.detect import detect_languages, detect_os_template
from gitignore_cli.file import GitignoreFile
from gitignore_cli.templates import get_store

MARKER = "# Managed by gitignore-cli"
TEMPLATE_DIR_NAME = "gitignore-cli"

POST_CHECKOUT_HOOK = "post-checkout"
PRE_PUSH_HOOK = "pre-push"

INIT_BODY = """\
# Create .gitignore when a repository is initialized (clone/checkout).
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
if [ ! -f "$root/.gitignore" ]; then
  gitignore create --path "$root" 2>/dev/null || true
fi
"""

SYNC_BODY = """\
# Sync .gitignore before pushing (update if present, create if missing).
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
if [ -f "$root/.gitignore" ]; then
  gitignore update --path "$root" 2>/dev/null || true
else
  gitignore create --path "$root" 2>/dev/null || true
fi
"""


@dataclass(frozen=True)
class HookSpec:
    name: str
    body: str
    run_on_install: bool = False


HOOKS = (
    HookSpec(POST_CHECKOUT_HOOK, INIT_BODY, run_on_install=True),
    HookSpec(PRE_PUSH_HOOK, SYNC_BODY),
)


def ensure_gitignore(repo_path: Path) -> bool:
    """Create .gitignore when it is missing. Returns True if a file was created."""
    gitignore_path = repo_path / ".gitignore"
    if gitignore_path.exists():
        return False

    ensure_detection_tools()
    store = get_store()
    os_template = detect_os_template()
    detected = detect_languages(repo_path, store)
    templates = [os_template, *sorted(detected)]
    document = GitignoreFile(path=gitignore_path)
    document.write(store, store.sort_templates(templates))
    return True


def sync_gitignore(repo_path: Path) -> None:
    """Update .gitignore when present, otherwise create it."""
    gitignore_path = repo_path / ".gitignore"
    if not gitignore_path.exists():
        ensure_gitignore(repo_path)
        return

    ensure_detection_tools()
    store = get_store()
    os_template = detect_os_template()
    document = GitignoreFile.load(gitignore_path, store)
    detected = detect_languages(repo_path, store)
    content = gitignore_path.read_text(encoding="utf-8")

    to_add: list[str] = []
    if not document.template_present(store, os_template, content):
        to_add.append(os_template)
    for template in sorted(detected):
        if not document.template_present(store, template, content):
            to_add.append(template)

    document.append_templates(store, to_add)


def find_git_dir(repo_path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (repo_path / git_dir).resolve()
    return git_dir


def hooks_dir(repo_path: Path) -> Path | None:
    git_dir = find_git_dir(repo_path)
    if git_dir is None:
        return None
    return git_dir / "hooks"


def global_template_dir() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    config_root = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return config_root / TEMPLATE_DIR_NAME / "template"


def _render_hook(spec: HookSpec) -> str:
    return f"#!/bin/sh\n{MARKER}\n{spec.body}"


def _append_block(spec: HookSpec) -> str:
    return f"\n# --- gitignore-cli: {spec.name} ---\n{MARKER}\n{spec.body}"


def install_hook_file(path: Path, spec: HookSpec) -> str:
    rendered = _render_hook(spec)
    if not path.exists():
        path.write_text(rendered, encoding="utf-8")
        path.chmod(0o755)
        return "installed"

    existing = path.read_text(encoding="utf-8")
    if MARKER in existing:
        path.write_text(rendered, encoding="utf-8")
        path.chmod(0o755)
        return "updated"

    path.write_text(existing.rstrip() + _append_block(spec) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return "appended"


def run_hook_body(spec: HookSpec, repo_path: Path) -> None:
    if spec.name == POST_CHECKOUT_HOOK:
        ensure_gitignore(repo_path)
        return

    sync_gitignore(repo_path)


def install_repo_hooks(repo_path: Path) -> list[tuple[str, str]]:
    target = hooks_dir(repo_path)
    if target is None:
        raise RuntimeError(f"{repo_path} is not inside a git repository.")

    results: list[tuple[str, str]] = []
    for spec in HOOKS:
        status = install_hook_file(target / spec.name, spec)
        results.append((spec.name, status))
        if spec.run_on_install:
            run_hook_body(spec, repo_path)
    return results


def install_global_template() -> Path:
    template_root = global_template_dir()
    hooks_target = template_root / "hooks"
    hooks_target.mkdir(parents=True, exist_ok=True)

    for spec in HOOKS:
        path = hooks_target / spec.name
        path.write_text(_render_hook(spec), encoding="utf-8")
        path.chmod(0o755)

    subprocess.run(
        ["git", "config", "--global", "init.templateDir", str(template_root)],
        check=True,
    )
    return template_root
