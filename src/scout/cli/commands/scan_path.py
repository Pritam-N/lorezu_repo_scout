from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import typer

from scout.cli.ui import (
    FindingsRenderOptions,
    get_ui,
    render_errors,
    render_findings_table,
    render_scan_summary,
    run_tui,
)
from scout.core.config import load_scan_config
from scout.core.errors import ExitCode
from scout.core.engine import run_scan
from scout.core.models import ScanTarget, TargetKind
from scout.rules.loader import load_ruleset
from scout.scanners.fs_scanner import read_text_candidate, scan_path as fs_scan_path
from scout.scanners.git_scanner import scan_git_repo


def _should_use_tui(plain: bool) -> bool:
    # TUI only when interactive to avoid breaking CI/pipes.
    if plain:
        return False
    return sys.stdout.isatty()


def scan_cmd(
    path: Optional[Path] = typer.Argument(
        None, help="Path to scan (repo root or any folder)."
    ),
    path_opt: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to scan (alternative to positional arg)."
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Disable TUI; print Rich output (CI-friendly)."
    ),
    fail: bool = typer.Option(
        True, "--fail/--no-fail", help="Exit 1 if findings are present (CI mode)."
    ),
    ignore_errors: bool = typer.Option(
        False, "--ignore-errors", help="Exit 0/1 even if some files error."
    ),
    include_ignored: Optional[bool] = typer.Option(
        None,
        "--include-ignored/--no-include-ignored",
        help="When scanning a git repo, include gitignored files (overrides config if set).",
    ),
    include_untracked: bool = typer.Option(
        True,
        "--include-untracked/--no-include-untracked",
        help="When scanning a git repo, include untracked files (default true).",
    ),
    ignore: List[str] = typer.Option(
        [],
        "--ignore",
        help="Glob(s) to ignore (repeatable), applied to relative paths.",
    ),
    rules_file: List[Path] = typer.Option(
        [],
        "--rules",
        exists=True,
        dir_okay=False,
        help="Additional rule pack files (repeatable). Highest precedence.",
    ),
    builtin: str = typer.Option(
        "default",
        "--builtin",
        help="Builtin rule pack name (e.g., default, strict) bundled with the CLI.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print config/rules sources and scan summary."
    ),
) -> None:
    """Scan a local path for secrets (auto-detects git repos)."""
    # Resolve path: --path takes precedence, then positional, then default to "."
    resolved_path: Path
    if path_opt is not None:
        resolved_path = path_opt
    elif path is not None:
        resolved_path = path
    else:
        resolved_path = Path(".")

    ui = get_ui(verbose=verbose)
    console = ui.console

    scan_root = resolved_path.resolve()

    # Load config (defaults -> global -> repo -> CLI overrides)
    cli_overrides = {"scan": {}}
    if include_ignored is not None:
        cli_overrides["scan"]["include_ignored"] = bool(include_ignored)

    loaded_cfg = load_scan_config(start_dir=scan_root, cli_overrides=cli_overrides)
    cfg = loaded_cfg.config

    # Load rules (builtin -> global -> repo -> extras)
    loaded_rules = load_ruleset(
        start_dir=scan_root, builtin=builtin, extra_rule_files=rules_file
    )
    ruleset = loaded_rules.ruleset

    if ui.verbose:
        console.print("[bold]Config sources:[/bold]")
        console.print(f"  global: {loaded_cfg.global_path or '-'}")
        console.print(f"  repo:   {loaded_cfg.repo_path or '-'}")
        console.print("[bold]Rule sources:[/bold]")
        for s in loaded_rules.sources:
            console.print(f"  - {s}")
        console.print()

    # Auto-detect git repo; fallback to filesystem scan
    try:
        git_root, git_candidates = scan_git_repo(
            start_dir=scan_root,
            config=cfg,
            include_untracked=include_untracked,
            include_ignored=include_ignored,
            ignore_globs=ignore,
        )
        target = ScanTarget(
            name=str(git_root),
            kind=TargetKind.LOCAL,
            root_path=str(git_root),
            meta={"scanner": "git"},
        )
        candidates_iter = git_candidates
    except Exception:
        target = ScanTarget(
            name=str(scan_root),
            kind=TargetKind.LOCAL,
            root_path=str(scan_root),
            meta={"scanner": "fs"},
        )
        candidates_iter = fs_scan_path(
            scan_root, cfg, ignore_globs=ignore, follow_symlinks=False
        )

    # Run scan
    result = run_scan(
        target=target,
        candidates=candidates_iter,
        ruleset=ruleset,
        config=cfg,
        read_text=lambda c: read_text_candidate(c, cfg),
        baseline=None,
        structured_parsers=None,  # add later
        dedupe=True,
    )

    # Default: TUI for humans (interactive terminals only)
    if _should_use_tui(plain):
        run_tui(findings=result.findings, errors=result.errors, result=result)
    else:
        render_findings_table(
            console,
            result.findings,
            opts=FindingsRenderOptions(
                title=f"Findings ({len(result.findings)})", group_by_target=False
            ),
        )
        render_errors(console, result.errors, verbose=ui.verbose)
        if ui.verbose:
            render_scan_summary(console, result, header="Summary")

    # Exit codes (still apply even if TUI was shown)
    if result.errors and not ignore_errors:
        raise typer.Exit(code=int(ExitCode.ERROR))

    if result.findings and fail:
        raise typer.Exit(code=int(ExitCode.FINDINGS))

    raise typer.Exit(code=int(ExitCode.OK))
