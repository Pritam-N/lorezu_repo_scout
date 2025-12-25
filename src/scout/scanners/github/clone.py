from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from scout.scanners.github.api import RepoInfo


@dataclass(frozen=True)
class CloneOptions:
    shallow: bool = True
    depth: int = 1
    blobless: bool = True  # uses --filter=blob:none where supported


def _run_git(args: list[str], *, cwd: Optional[Path] = None, env: Optional[dict[str, str]] = None) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")


def clone_repo(
    repo: RepoInfo,
    dest_root: Path,
    *,
    token: Optional[str],
    opts: CloneOptions,
) -> Path:
    """
    Clone repo into dest_root/<owner>__<name>.
    Auth is done via git http.extraheader (no token in URL).
    """
    dest_root.mkdir(parents=True, exist_ok=True)
    safe_dir = f"{repo.owner_login}__{repo.name}".replace("/", "__")
    dest = (dest_root / safe_dir).resolve()

    # If folder exists from previous run, remove it (caller can set keep_clones if desired)
    if dest.exists():
        # be safe: only delete if it's inside dest_root
        if dest_root.resolve() in dest.parents:
            for p in sorted(dest.rglob("*"), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                    else:
                        p.rmdir()
                except Exception:
                    pass
            try:
                dest.rmdir()
            except Exception:
                pass

    clone_url = repo.clone_url
    args = ["clone"]

    if opts.shallow:
        args += ["--depth", str(max(1, int(opts.depth)))]

    # blobless clone speeds scanning drastically (requires newer git + server support)
    if opts.blobless:
        args += ["--filter=blob:none"]

    args += [clone_url, str(dest)]

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    # Auth: send bearer token header to github.com
    # NOTE: header name is case-insensitive; Git expects "AUTHORIZATION: ..."
    extra = None
    if token:
        extra = f"AUTHORIZATION: bearer {token}"
        args = ["-c", f"http.extraheader={extra}", *args]

    _run_git(args, env=env)

    # Ensure we have a working tree in HEAD
    # Some repos might have default branch not checked out if unusual; git clone handles it typically.
    return dest