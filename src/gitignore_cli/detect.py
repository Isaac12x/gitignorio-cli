from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from gitignore_cli.deps import _linguist_commands, extended_env
from gitignore_cli.mapping import SKIP_MAGIKA_LABELS, resolve_template
from gitignore_cli.templates import TemplateStore

EXTENSION_MAP: dict[str, str] = {
    ".c": "c",
    ".cc": "c++",
    ".cpp": "c++",
    ".cs": "csharp",
    ".dart": "dart",
    ".el": "emacs",
    ".ex": "elixir",
    ".exs": "elixir",
    ".go": "go",
    ".gradle": "gradle",
    ".hs": "haskell",
    ".java": "java",
    ".jl": "julia",
    ".js": "node",
    ".jsx": "react",
    ".kt": "kotlin",
    ".less": "less",
    ".lua": "lua",
    ".m": "objective-c",
    ".mm": "objective-c",
    ".php": "composer",
    ".pl": "perl",
    ".py": "python",
    ".r": "r",
    ".rb": "ruby",
    ".rs": "rust",
    ".sass": "sass",
    ".scala": "scala",
    ".scss": "sass",
    ".sql": "database",
    ".svelte": "svelte",
    ".swift": "swift",
    ".ts": "node",
    ".tsx": "react",
    ".vue": "vue",
    ".zig": "zig",
}

SPECIAL_FILES: dict[str, str] = {
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "go.mod": "go",
    "package.json": "node",
    "Pipfile": "python",
    "pyproject.toml": "python",
    "requirements.txt": "python",
}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
}


def detect_os_template() -> str:
    import sys

    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    return "linux"


def _parse_linguist_breakdown(output: str, store: TemplateStore) -> set[str]:
    templates: set[str] = set()
    for line in output.splitlines():
        match = re.match(r"^\s*[\d.]+%\s+\d+\s+(.+?)\s*$", line)
        if not match:
            continue
        language = match.group(1).strip()
        if language.lower() in {"markdown", "text", "json", "yaml", "xml", "csv"}:
            continue
        resolved = resolve_template(language, store.available)
        if resolved:
            templates.add(resolved)
    return templates


def _parse_magika_json(output: str, store: TemplateStore) -> set[str]:
    templates: set[str] = set()
    try:
        entries = json.loads(output)
    except json.JSONDecodeError:
        return templates

    if not isinstance(entries, list):
        return templates

    for entry in entries:
        path = entry.get("path", "")
        if "/.git/" in path.replace("\\", "/") or path.endswith("/.git"):
            continue

        result = entry.get("result", {})
        if result.get("status") != "ok":
            continue

        label = result.get("value", {}).get("output", {}).get("label", "")
        if not label or label in SKIP_MAGIKA_LABELS:
            continue

        resolved = resolve_template(label, store.available)
        if not resolved:
            resolved = resolve_template(label.replace("_", " "), store.available)
        if resolved:
            templates.add(resolved)

    return templates


def _detect_from_extensions(repo_path: Path, store: TemplateStore) -> set[str]:
    templates: set[str] = set()
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        special = SPECIAL_FILES.get(path.name)
        if special:
            resolved = resolve_template(special, store.available)
            if resolved:
                templates.add(resolved)

        suffix = path.suffix.lower()
        mapped = EXTENSION_MAP.get(suffix)
        if not mapped:
            continue
        resolved = resolve_template(mapped, store.available)
        if resolved:
            templates.add(resolved)
    return templates


def _has_extension(repo_path: Path, suffix: str) -> bool:
    for path in repo_path.rglob(f"*{suffix}"):
        if path.is_file() and not any(part in IGNORED_DIRS for part in path.parts):
            return True
    return False


def _refine_detected(repo_path: Path, detected: set[str]) -> set[str]:
    refined = set(detected)
    if "python" in refined and "lua" in refined and not _has_extension(repo_path, ".lua"):
        refined.discard("lua")
    return refined


def _run_linguist(repo_path: Path) -> subprocess.CompletedProcess[str]:
    last_result: subprocess.CompletedProcess[str] | None = None
    for cmd in _linguist_commands(["--breakdown"]):
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            env=extended_env(),
            timeout=120,
        )
        last_result = result
        if result.returncode == 0:
            return result
    assert last_result is not None
    return last_result


def detect_languages(repo_path: Path, store: TemplateStore) -> set[str]:
    repo_path = repo_path.resolve()
    detected = _detect_from_extensions(repo_path, store)

    linguist = _run_linguist(repo_path)
    if linguist.returncode == 0:
        detected |= _parse_linguist_breakdown(linguist.stdout, store)

    magika = subprocess.run(
        ["magika", "--json", "-r", str(repo_path)],
        capture_output=True,
        text=True,
        check=False,
        env=extended_env(),
        timeout=300,
    )
    if magika.returncode == 0:
        detected |= _parse_magika_json(magika.stdout, store)

    detected = _refine_detected(repo_path, detected)
    detected.discard(detect_os_template())
    return detected


def normalize_user_template(name: str, store: TemplateStore) -> str:
    resolved = resolve_template(name, store.available)
    if not resolved:
        raise ValueError(
            f"Unknown gitignore template '{name}'. "
            "Run `gitignore list` or see https://www.toptal.com/developers/gitignore/api/list"
        )
    return resolved
