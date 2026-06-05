from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from gitignore_cli.deps import ensure_detection_tools
from gitignore_cli.detect import detect_languages, detect_os_template, normalize_user_template
from gitignore_cli.file import GitignoreFile
from gitignore_cli.global_gitignore import (
    detect_editors,
    get_global_gitignore_path,
    install_global,
    update_global,
)
from gitignore_cli.hooks import install_global_template, install_repo_hooks
from gitignore_cli.templates import get_store

app = typer.Typer(
    no_args_is_help=True,
    help="Create and update .gitignore files using gitignore.io with automatic language detection.",
)


def _repo_path(path: Optional[Path]) -> Path:
    return (path or Path.cwd()).resolve()


def _gitignore_path(repo_path: Path) -> Path:
    return repo_path / ".gitignore"


@app.command()
def create(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
    no_detect: bool = typer.Option(
        False,
        "--no-detect",
        help="Only add the current operating system template.",
    ),
) -> None:
    """Create a .gitignore with the current OS template and detected languages."""
    ensure_detection_tools()
    repo_path = _repo_path(path)
    gitignore_path = _gitignore_path(repo_path)
    store = get_store()
    os_template = detect_os_template()

    if gitignore_path.exists():
        typer.echo(f".gitignore already exists at {gitignore_path}", err=True)
        raise typer.Exit(code=1)

    templates = [os_template]
    if not no_detect:
        detected = detect_languages(repo_path, store)
        templates.extend(sorted(detected))

    document = GitignoreFile(path=gitignore_path)
    document.write(store, store.sort_templates(templates))
    typer.echo(f"Created {gitignore_path} with templates: {', '.join(store.sort_templates(templates))}")


@app.command()
def update(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Update .gitignore by appending newly detected languages."""
    ensure_detection_tools()
    repo_path = _repo_path(path)
    gitignore_path = _gitignore_path(repo_path)
    store = get_store()
    os_template = detect_os_template()

    if not gitignore_path.exists():
        typer.echo(f"No .gitignore found at {gitignore_path}. Run `gi create` first.", err=True)
        raise typer.Exit(code=1)

    document = GitignoreFile.load(gitignore_path, store)
    detected = detect_languages(repo_path, store)
    content = gitignore_path.read_text(encoding="utf-8")

    to_add: list[str] = []
    if not document.template_present(store, os_template, content):
        to_add.append(os_template)
    for template in sorted(detected):
        if not document.template_present(store, template, content):
            to_add.append(template)

    added = document.append_templates(store, to_add)
    if added:
        typer.echo(f"Added: {', '.join(added)}")
        typer.echo(f"Updated {gitignore_path}")
    else:
        typer.echo("No changes needed.")


@app.command()
def add(
    languages: list[str] = typer.Argument(..., help="gitignore.io template names to append."),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Append gitignore templates that are not already present."""
    repo_path = _repo_path(path)
    gitignore_path = _gitignore_path(repo_path)
    store = get_store()

    if not gitignore_path.exists():
        typer.echo(f"No .gitignore found at {gitignore_path}. Run `gi create` first.", err=True)
        raise typer.Exit(code=1)

    document = GitignoreFile.load(gitignore_path, store)
    content = gitignore_path.read_text(encoding="utf-8")
    to_add: list[str] = []
    skipped: list[str] = []

    for language in languages:
        try:
            template = normalize_user_template(language, store)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        if document.template_present(store, template, content):
            skipped.append(template)
        else:
            to_add.append(template)

    added = document.append_templates(store, to_add)
    if added:
        typer.echo(f"Added: {', '.join(added)}")
    if skipped:
        typer.echo(f"Already present: {', '.join(skipped)}")
    if not added and skipped:
        typer.echo("Nothing to do.")


@app.command("list")
def list_templates() -> None:
    """List available gitignore.io templates."""
    store = get_store()
    for template in store.sort_templates(list(store.available)):
        typer.echo(template)


global_app = typer.Typer(help="Manage the user-level global gitignore (~/.gitignore_global).")
app.add_typer(global_app, name="global")


@global_app.command("install")
def global_install(
    editor: list[str] = typer.Option(
        [],
        "--editor",
        "-e",
        help="Editor template to include (repeatable). Example: --editor vim --editor vscode",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Override path for the global gitignore file.",
    ),
    no_detect: bool = typer.Option(
        False,
        "--no-detect",
        help="Skip automatic editor detection; only include the OS template.",
    ),
) -> None:
    """Create or overwrite the global gitignore and configure core.excludesFile."""
    editors: list[str] | None = list(editor) if editor else None
    if no_detect:
        editors = list(editor)

    global_path, templates, detected = install_global(
        editors=editors,
        path=path,
        detect=not no_detect,
    )
    typer.echo(f"Created {global_path} with templates: {', '.join(templates)}")
    if detected:
        typer.echo(f"Auto-detected editors: {', '.join(detected)}")
    typer.echo(f"Configured git config --global core.excludesFile={global_path}")


@global_app.command("update")
def global_update_cmd(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Override path for the global gitignore file.",
    ),
) -> None:
    """Append any missing OS template to the global gitignore (non-destructive)."""
    global_path, added = update_global(path=path)
    if added:
        typer.echo(f"Added: {', '.join(added)}")
        typer.echo(f"Updated {global_path}")
    else:
        typer.echo("No changes needed.")


@global_app.command("show")
def global_show() -> None:
    """Print the global gitignore path and its contents."""
    path = get_global_gitignore_path()
    typer.echo(f"# Path: {path}")
    if path.exists():
        typer.echo(path.read_text(encoding="utf-8"))
    else:
        typer.echo("# File does not exist. Run `gi global install` to create it.")


hooks_app = typer.Typer(help="Install git hooks for automatic .gitignore management.")
app.add_typer(hooks_app, name="hooks")


@hooks_app.command("install")
def hooks_install(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
    global_template: bool = typer.Option(
        False,
        "--global",
        help="Also install hooks into the global git init template for new repositories.",
    ),
) -> None:
    """Install post-checkout and pre-push hooks (create or update existing hook scripts)."""
    repo_path = _repo_path(path)
    try:
        results = install_repo_hooks(repo_path)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for name, status in results:
        typer.echo(f"{status.capitalize()} {name} hook")

    if global_template:
        template_dir = install_global_template()
        typer.echo(f"Configured global init.templateDir at {template_dir}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
