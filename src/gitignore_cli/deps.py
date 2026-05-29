from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def extended_env() -> dict[str, str]:
    env = os.environ.copy()
    extra_paths: list[str] = []
    home = Path.home()
    for candidate in (
        home / ".rbenv" / "shims",
        home / ".local" / "bin",
        home / ".gem" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ):
        if candidate.is_dir():
            extra_paths.append(str(candidate))
    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths + [env.get("PATH", "")])
    return env


def _run(cmd: list[str], *, timeout: int = 300) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=extended_env(), timeout=timeout)


def _linguist_commands(args: list[str]) -> list[list[str]]:
    commands = [
        ["github-linguist", *args],
        ["bash", "-lc", f"github-linguist {' '.join(args)}"],
    ]
    if shutil.which("rbenv"):
        commands.insert(0, ["bash", "-lc", f"RBENV_VERSION=3.4.5 github-linguist {' '.join(args)}"])
    return commands


def _linguist_available() -> bool:
    for cmd in _linguist_commands(["--version"]):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=extended_env(),
            timeout=30,
        )
        if result.returncode == 0:
            return True
    return False


def ensure_github_linguist() -> None:
    if _linguist_available():
        return

    if not shutil.which("gem"):
        raise RuntimeError(
            "github-linguist is not installed and Ruby gem is unavailable. "
            "Install Ruby, then run: gem install github-linguist"
        )

    _run(["gem", "install", "github-linguist"], timeout=600)
    if not _linguist_available():
        raise RuntimeError(
            "Installed github-linguist, but it is still unavailable in PATH. "
            "Ensure your Ruby shims are on PATH, then retry."
        )


def ensure_pipx() -> None:
    if shutil.which("pipx"):
        return

    if sys.platform == "darwin" and shutil.which("brew"):
        _run(["brew", "install", "pipx"])
        _run(["pipx", "ensurepath"])
        return

    python = shutil.which("python3") or shutil.which("python")
    if not python:
        raise RuntimeError(
            "pipx is not installed. Install pipx first, for example:\n"
            "  brew install pipx && pipx ensurepath   # macOS\n"
            "  python3 -m pip install --user pipx && python3 -m pipx ensurepath"
        )

    _run([python, "-m", "pip", "install", "--user", "pipx"])
    _run([python, "-m", "pipx", "ensurepath"])


def ensure_magika() -> None:
    if shutil.which("magika"):
        return

    ensure_pipx()
    _run(["pipx", "install", "magika"], timeout=600)


def ensure_detection_tools() -> None:
    ensure_github_linguist()
    ensure_magika()
