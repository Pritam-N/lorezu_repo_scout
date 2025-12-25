from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator, List, Optional, Set

from scout.core.models import FileCandidate, ScanConfig
from scout.core.matcher import any_glob_match, normalize_rel_path


def _run_git(cwd: Path, args: List[str]) -> bytes:
    """
    Run a git command and return stdout (bytes).
    Raises RuntimeError on failure.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return proc.stdout


def _git_root(start_dir: Path) -> Path:
    out = _run_git(start_dir, ["rev-parse", "--show-toplevel"])
    s = out.decode("utf-8", errors="replace").strip()
    return Path(s).resolve()


def _split_nul_paths(data: bytes) -> List[str]:
    if not data:
        return []
    parts = data.split(b"\x00")
    return [p.decode("utf-8", errors="replace") for p in parts if p]


def _path_has_skip_dir(rel_path: str, skip_dirs: Set[str]) -> bool:
    # Compare path components against skip dir basenames
    for part in rel_path.split("/"):
        if part in skip_dirs:
            return True
    return False


def scan_git_repo(
    start_dir: Path,
    config: ScanConfig,
    *,
    include_untracked: bool = True,
    include_ignored: Optional[bool] = None,
    ignore_globs: Optional[List[str]] = None,
) -> tuple[Path, Iterator[FileCandidate]]:
    """
    Enumerate git files (tracked + optional untracked + optional ignored) and yield FileCandidates.

    Returns: (git_root, iterator)

    Notes:
    - Uses `git ls-files` so it’s fast and avoids walking vendor dirs not tracked.
    - Still applies config.skip_dirs and ignore_globs as an extra safety net.
    """
    include_ignored = config.include_ignored if include_ignored is None else include_ignored
    ignore_globs = ignore_globs or []
    skip_dirs = set(config.skip_dirs)

    root = _git_root(start_dir)

    # Tracked files
    tracked = set(_split_nul_paths(_run_git(root, ["ls-files", "-z"])))

    # Untracked (excluding ignored)
    others: Set[str] = set()
    if include_untracked:
        others |= set(_split_nul_paths(_run_git(root, ["ls-files", "-z", "--others", "--exclude-standard"])))

    # Ignored files (optional)
    ignored: Set[str] = set()
    if include_untracked and include_ignored:
        # -i => ignored, --others => non-tracked
        ignored |= set(_split_nul_paths(_run_git(root, ["ls-files", "-z", "--others", "-i", "--exclude-standard"])))

    all_paths = tracked | others | ignored

    def _iter() -> Iterator[FileCandidate]:
        ordered = sorted(all_paths) if config.deterministic else list(all_paths)

        for rel in ordered:
            rel_norm = normalize_rel_path(rel)

            # Skip directories by name
            if _path_has_skip_dir(rel_norm, skip_dirs):
                continue

            # Optional ignore globs
            if ignore_globs and any_glob_match(rel_norm, ignore_globs):
                continue

            abs_path = (root / rel_norm)
            try:
                if not abs_path.is_file():
                    continue
            except OSError:
                continue

            try:
                size = int(abs_path.stat().st_size)
            except OSError:
                size = 0

            # Git scanner: cheap binary sniff (NUL byte)
            is_binary = _is_probably_binary(abs_path)

            yield FileCandidate(
                abs_path=str(abs_path),
                rel_path=rel_norm,
                size_bytes=size,
                is_binary=is_binary,
                extension=abs_path.suffix.lower() or None,
            )

    return root, _iter()


def _is_probably_binary(path: Path, sniff_bytes: int = 8192) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(sniff_bytes)
    except OSError:
        return True
    return b"\x00" in chunk