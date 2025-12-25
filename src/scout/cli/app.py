from __future__ import annotations

import typer
from rich.console import Console

# Root Typer app
app = typer.Typer(
    name="secret-scout",
    help="Prevent accidental secret leaks by scanning repos for risky files and patterns.",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()


# --- Commands / Sub-apps ---
# Keep these imports inside try/except if you're still building modules incrementally.

from scout.cli.commands.init import app as init_app  # noqa: E402

# Mount subcommands
app.add_typer(init_app, name="project")  # secret-scout project init


# Optional: convenience alias so you can do `secret-scout init`
@app.command("init")
def init_alias(
    directory: str = typer.Argument(".", help="Repo directory to initialize"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    strict: bool = typer.Option(
        False, "--strict", help="Generate strict starter rules template."
    ),
    no_gitignore: bool = typer.Option(
        False, "--no-gitignore", help="Do not create .secret-scout/.gitignore"
    ),
    no_readme: bool = typer.Option(
        False, "--no-readme", help="Do not create .secret-scout/README.md"
    ),
) -> None:
    # Import the command function directly to avoid circular imports
    from pathlib import Path
    from scout.cli.commands.init import init_cmd  # noqa: E402

    init_cmd(
        directory=Path(directory),
        force=force,
        strict=strict,
        no_gitignore=no_gitignore,
        no_readme=no_readme,
    )


from scout.cli.commands.scan_path import scan_cmd  # noqa: E402

# Register scan command directly: secret-scout scan . OR secret-scout scan --path .
app.command("scan")(scan_cmd)

from scout.cli.commands.scan_github import app as scan_github_app  # noqa: E402

app.add_typer(scan_github_app, name="github")  # secret-scout github --org OR --user
