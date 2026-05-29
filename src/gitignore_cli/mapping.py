from __future__ import annotations

import re

# Linguist language names and magika labels mapped to gitignore.io template keys.
LANGUAGE_ALIASES: dict[str, str] = {
    "c#": "csharp",
    "c++": "c++",
    "clojure": "clojure",
    "common lisp": "commonlisp",
    "crystal": "crystal",
    "css": "web",
    "dart": "dart",
    "elixir": "elixir",
    "elm": "elm",
    "erlang": "erlang",
    "f#": "fsharp",
    "fortran": "fortran",
    "go": "go",
    "groovy": "groovy",
    "haskell": "haskell",
    "html": "web",
    "java": "java",
    "javascript": "node",
    "js": "node",
    "jsonnet": "jsonnet",
    "julia": "julia",
    "kotlin": "kotlin",
    "less": "less",
    "lua": "lua",
    "makefile": "cmake",
    "nim": "nim",
    "objective-c": "objective-c",
    "ocaml": "ocaml",
    "perl": "perl",
    "php": "composer",
    "powershell": "powershell",
    "python": "python",
    "r": "r",
    "ruby": "ruby",
    "rust": "rust",
    "scala": "scala",
    "scheme": "scheme",
    "solidity": "solidity",
    "sql": "database",
    "svelte": "svelte",
    "swift": "swift",
    "typescript": "node",
    "tsx": "node",
    "tsxreact": "react",
    "vue": "vue",
    "zig": "zig",
}

OS_TEMPLATES = frozenset({"linux", "macos", "osx", "windows"})

SKIP_MAGIKA_LABELS = frozenset(
    {
        "asm",
        "batch",
        "binary",
        "csv",
        "doc",
        "docx",
        "email",
        "ignorefile",
        "ini",
        "json",
        "markdown",
        "pdf",
        "pem",
        "pptx",
        "rtf",
        "shell",
        "svg",
        "toml",
        "txt",
        "unknown",
        "xlsx",
        "xml",
        "yaml",
        "yml",
    }
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", value.lower())


def resolve_template(name: str, available: set[str]) -> str | None:
    lowered = name.lower().strip()
    if lowered in available:
        return lowered

    alias = LANGUAGE_ALIASES.get(lowered)
    if alias and alias in available:
        return alias

    normalized = normalize_key(lowered)
    for candidate in available:
        if normalize_key(candidate) == normalized:
            return candidate

    alias = LANGUAGE_ALIASES.get(normalized)
    if alias and alias in available:
        return alias

    return None
