from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from gitignore_cli.deps import _linguist_commands, extended_env
from gitignore_cli.ignored_dirs import dir_name_is_ignored, path_is_ignored
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

_MAGIKA_BATCH_SIZE = 500


def _walk_repo_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []

    def walk(directory: Path) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if dir_name_is_ignored(entry.name):
                continue
            if entry.is_file():
                files.append(entry)
            elif entry.is_dir():
                walk(entry)

    walk(repo_path)
    return files


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
        if path_is_ignored(path):
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
    for path in _walk_repo_files(repo_path):

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
    suffix = suffix.lower()
    return any(path.suffix.lower() == suffix for path in _walk_repo_files(repo_path))


def _refine_detected(repo_path: Path, detected: set[str]) -> set[str]:
    refined = set(detected)
    if "python" in refined and "lua" in refined and not _has_extension(repo_path, ".lua"):
        refined.discard("lua")
    return refined


def _run_magika(repo_path: Path) -> str | None:
    files = _walk_repo_files(repo_path)
    if not files:
        return "[]"

    combined: list[dict] = []
    for start in range(0, len(files), _MAGIKA_BATCH_SIZE):
        batch = files[start : start + _MAGIKA_BATCH_SIZE]
        result = subprocess.run(
            ["magika", "--json", *[str(path) for path in batch]],
            capture_output=True,
            text=True,
            check=False,
            env=extended_env(),
            timeout=300,
        )
        if result.returncode != 0:
            return None
        try:
            entries = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if isinstance(entries, list):
            combined.extend(entries)

    return json.dumps(combined)


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

    magika_output = _run_magika(repo_path)
    if magika_output is not None:
        detected |= _parse_magika_json(magika_output, store)

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
