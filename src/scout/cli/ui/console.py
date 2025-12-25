from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.theme import Theme


DEFAULT_THEME = Theme(
    {
        "ok": "green",
        "warn": "yellow",
        "err": "red",
        "muted": "dim",
        "sev.critical": "bold red",
        "sev.high": "magenta",
        "sev.medium": "yellow",
        "sev.low": "cyan",
        "path": "white",
        "rule": "bold",
    }
)


@dataclass(frozen=True)
class UIContext:
    """
    Shared UI context for consistent output formatting across commands.
    """
    console: Console
    verbose: bool = False
    json: bool = False  # reserved for future JSON output mode


_default_ctx: Optional[UIContext] = None


def get_ui(verbose: bool = False, *, force_new: bool = False) -> UIContext:
    """
    Get a shared Rich Console configured with a theme.
    """
    global _default_ctx
    if _default_ctx is None or force_new:
        _default_ctx = UIContext(console=Console(theme=DEFAULT_THEME), verbose=verbose)
    else:
        # update verbosity on reuse (safe)
        _default_ctx = UIContext(console=_default_ctx.console, verbose=verbose, json=_default_ctx.json)
    return _default_ctx