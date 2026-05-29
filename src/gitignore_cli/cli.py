from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from gitignore_cli.deps import ensure_detection_tools
from gitignore_cli.detect import detect_languages, detect_os_template, normalize_user_template
from gitignore_cli.file import GitignoreFile
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
    """Update .gitignore by adding newly detected languages and removing unused ones."""
    ensure_detection_tools()
    repo_path = _repo_path(path)
    gitignore_path = _gitignore_path(repo_path)
    store = get_store()
    os_template = detect_os_template()

    if not gitignore_path.exists():
        typer.echo(f"No .gitignore found at {gitignore_path}. Run `gitignore create` first.", err=True)
        raise typer.Exit(code=1)

    document = GitignoreFile.load(gitignore_path, store)
    detected = detect_languages(repo_path, store)

    if not document.managed:
        added: list[str] = []
        if not document.templates:
            document.templates = [os_template]
            document.managed = True
        for template in sorted(detected):
            if document.add_template(store, template):
                added.append(template)
        document.write(store, store.sort_templates(document.templates))
        if added:
            typer.echo(f"Added: {', '.join(added)}")
            typer.echo(f"Updated {gitignore_path}")
        else:
            typer.echo("No changes needed.")
        return

    templates, added, removed = document.update_templates(
        store,
        os_template=os_template,
        detected_languages=detected,
    )
    document.write(store, templates)

    if added:
        typer.echo(f"Added: {', '.join(added)}")
    if removed:
        typer.echo(f"Removed: {', '.join(removed)}")
    if not added and not removed:
        typer.echo("No changes needed.")
    else:
        typer.echo(f"Updated {gitignore_path}")


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
        typer.echo(f"No .gitignore found at {gitignore_path}. Run `gitignore create` first.", err=True)
        raise typer.Exit(code=1)

    document = GitignoreFile.load(gitignore_path, store)
    added: list[str] = []
    skipped: list[str] = []

    for language in languages:
        try:
            template = normalize_user_template(language, store)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        if document.add_template(store, template):
            added.append(template)
        else:
            skipped.append(template)

    if not document.templates:
        document.templates = [detect_os_template()]
        document.managed = True

    if added:
        document.write(store, store.sort_templates(document.templates))
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
