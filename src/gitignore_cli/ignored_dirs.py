"""Directory names skipped during language detection.

Any path component matching one of these names (case-insensitively) is not
walked or scanned. Covers third-party dependencies, package caches, and common
build output directories across languages and frameworks.
"""

from __future__ import annotations

from pathlib import Path

# Stored lowercase; matched case-insensitively against each path component.
IGNORED_DIRS = frozenset(
    {
        # Version control
        ".git",
        ".hg",
        ".svn",
        # Python
        "__pycache__",
        ".eggs",
        ".hypothesis",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "env",
        "site-packages",
        "venv",
        # JavaScript / Node / front-end package managers
        ".pnp",
        ".yarn",
        "bower_components",
        "jspm_packages",
        "node_modules",
        # PHP / Ruby / Composer / Bundler
        ".bundle",
        "vendor",
        "vendors",
        # Java / JVM / Android
        ".gradle",
        ".ivy2",
        ".m2",
        ".sbt",
        "target",
        # .NET / NuGet
        ".nuget",
        "packages",
        # Go
        "godeps",
        # Rust / Cargo (target covered above)
        # Elixir / Erlang / Phoenix
        "_build",
        "_checkouts",
        "deps",
        # Haskell / Stack
        ".stack-work",
        # Swift / iOS / CocoaPods / Carthage / Xcode
        "carthage",
        "deriveddata",
        "deriveddatacache",
        "pods",
        # C / C++ / cross-language vendoring conventions
        "3rdparty",
        "dependencies",
        "external",
        "externals",
        "third-party",
        "third_party",
        # Dart / Flutter
        ".dart_tool",
        ".pub-cache",
        # Scala / Metals / Bloop
        ".bloop",
        ".metals",
        # Zig
        "zig-cache",
        "zig-out",
        # Unity / game engines (generated local package cache)
        "library",
        # Other dependency layouts
        "_esy",
        "_vendor",
        "xvba_modules",
        # Common build / distribution output
        "build",
        "dist",
        "out",
    }
)


def dir_name_is_ignored(name: str) -> bool:
    return name.lower() in IGNORED_DIRS


def path_is_ignored(path: Path | str) -> bool:
    return any(dir_name_is_ignored(part) for part in Path(path).parts)
