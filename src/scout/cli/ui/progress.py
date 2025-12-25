from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table


@dataclass
class ProgressTasks:
    overall: TaskID
    cloning: TaskID
    scanning: TaskID


def build_progress(console: Console) -> Progress:
    """
    Standard progress layout used across commands.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}[/bold]"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,  # clears the progress bar after completion
    )


def init_tasks(progress: Progress, total_repos: int) -> ProgressTasks:
    overall = progress.add_task("Overall", total=total_repos)
    cloning = progress.add_task("Cloning", total=total_repos)
    scanning = progress.add_task("Scanning", total=total_repos)
    return ProgressTasks(overall=overall, cloning=cloning, scanning=scanning)


def bump(progress: Progress, task: TaskID, advance: int = 1) -> None:
    try:
        progress.update(task, advance=advance)
    except Exception:
        # be resilient; progress should never break scans
        pass


def render_phase_summary(console: Console, *, repos: int, cloned: int, scanned: int) -> None:
    """
    Optional final summary table for the phases.
    """
    t = Table(title="GitHub scan phases")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("Repos selected", str(repos))
    t.add_row("Repos cloned", str(cloned))
    t.add_row("Repos scanned", str(scanned))
    console.print(t)