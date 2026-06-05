from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from gitignore_cli.detect import detect_os_template, normalize_user_template
from gitignore_cli.file import GitignoreFile
from gitignore_cli.templates import get_store

DEFAULT_GLOBAL_PATH = Path.home() / ".gitignore_global"

# editor template name -> app paths (macOS) or bin names to probe
_EDITOR_APPS: dict[str, list[str]] = {
    "jetbrains+all": [
        "/Applications/IntelliJ IDEA.app",
        "/Applications/PyCharm.app",
        "/Applications/PyCharm CE.app",
        "/Applications/WebStorm.app",
        "/Applications/GoLand.app",
        "/Applications/CLion.app",
        "/Applications/Rider.app",
        "/Applications/DataGrip.app",
        "/Applications/RubyMine.app",
        "/Applications/Android Studio.app",
        "/Applications/Fleet.app",
    ],
    "visualstudiocode": [
        "/Applications/Visual Studio Code.app",
        "/Applications/Visual Studio Code - Insiders.app",
        "/Applications/Cursor.app",
    ],
    "sublimetext": ["/Applications/Sublime Text.app"],
    "xcode": ["/Applications/Xcode.app"],
    "eclipse": ["/Applications/Eclipse.app"],
}

_EDITOR_BINS: dict[str, list[str]] = {
    "vim": ["vim", "nvim"],
    "emacs": ["emacs"],
    "visualstudiocode": ["code", "cursor"],
    "sublimetext": ["subl"],
}


def get_global_gitignore_path() -> Path:
    result = subprocess.run(
        ["git", "config", "--global", "core.excludesFile"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        raw = result.stdout.strip()
        expanded = Path(raw).expanduser()
        return expanded
    return DEFAULT_GLOBAL_PATH


def detect_editors() -> list[str]:
    detected: list[str] = []
    for template, apps in _EDITOR_APPS.items():
        if any(Path(app).exists() for app in apps):
            if template not in detected:
                detected.append(template)
    for template, bins in _EDITOR_BINS.items():
        if any(shutil.which(b) for b in bins):
            if template not in detected:
                detected.append(template)
    return detected


def install_global(
    editors: list[str] | None = None,
    path: Path | None = None,
    detect: bool = True,
) -> tuple[Path, list[str], list[str]]:
    """Create or overwrite the global gitignore.

    Returns (path, templates_used, detected_editors).
    """
    global_path = path or get_global_gitignore_path()
    store = get_store()
    os_template = detect_os_template()

    if editors is None and detect:
        editors = detect_editors()
    elif editors is None:
        editors = []

    valid_editors: list[str] = []
    for editor in editors:
        try:
            valid_editors.append(normalize_user_template(editor, store))
        except ValueError:
            pass

    templates = store.sort_templates([os_template] + valid_editors)
    global_path.parent.mkdir(parents=True, exist_ok=True)
    document = GitignoreFile(path=global_path)
    document.write(store, templates)

    current_configured = _read_git_excludes_file()
    if current_configured != str(global_path):
        subprocess.run(
            ["git", "config", "--global", "core.excludesFile", str(global_path)],
            check=True,
        )

    return global_path, templates, valid_editors


def update_global(path: Path | None = None) -> tuple[Path, list[str]]:
    """Append missing OS template to the global gitignore (non-destructive)."""
    global_path = path or get_global_gitignore_path()
    store = get_store()
    os_template = detect_os_template()

    if not global_path.exists():
        result_path, templates, _ = install_global(path=global_path)
        return result_path, templates

    document = GitignoreFile.load(global_path, store)
    content = global_path.read_text(encoding="utf-8")

    to_add: list[str] = []
    if not document.template_present(store, os_template, content):
        to_add.append(os_template)

    added = document.append_templates(store, to_add)
    return global_path, added


def _read_git_excludes_file() -> str:
    result = subprocess.run(
        ["git", "config", "--global", "core.excludesFile"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""
