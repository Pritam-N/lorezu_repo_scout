from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from scout.core.models import FileCandidate, ScanConfig
from scout.core.matcher import any_glob_match, normalize_rel_path


_BINARY_SNIFF_BYTES = 8192


def is_probably_binary(path: Path, sniff_bytes: int = _BINARY_SNIFF_BYTES) -> bool:
    """
    Heuristic binary detection:
    - NUL byte => binary
    - otherwise treat as text
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(sniff_bytes)
    except OSError:
        # unreadable -> treat as binary-ish to avoid text processing
        return True

    if b"\x00" in chunk:
        return True
    return False


def read_text_candidate(candidate: FileCandidate, config: ScanConfig) -> Optional[str]:
    """
    Safe reader for policy.py:
    - returns None for binary files
    - returns None for files too large
    - tries utf-8 then latin-1 fallback
    """
    try:
        p = Path(candidate.abs_path)
    except Exception:
        return None

    if candidate.is_binary:
        return None
    if candidate.size_bytes > config.max_file_bytes:
        return None

    # Prefer utf-8, fallback to latin-1; always replace errors
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    except UnicodeError:
        try:
            return p.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return None


def _should_skip_dir(dirname: str, skip_dirs: set[str]) -> bool:
    return dirname in skip_dirs


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return True


def scan_path(
    root: Path,
    config: ScanConfig,
    *,
    ignore_globs: Optional[List[str]] = None,
    follow_symlinks: bool = False,
) -> Iterator[FileCandidate]:
    """
    Walk a directory tree and yield FileCandidates.

    Notes:
    - Applies skip_dirs pruning at directory-walk level (fast).
    - Applies ignore_globs to rel_path (glob match).
    - Marks is_binary + size_bytes (engine can skip quickly).
    - Does NOT read full contents here.
    """
    root = root.resolve()
    ignore_globs = ignore_globs or []
    skip_dirs = set(config.skip_dirs)

    # Ensure deterministic ordering for CI
    def maybe_sort(xs: List[str]) -> None:
        if config.deterministic:
            xs.sort()

    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        # Prune directories by basename
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d, skip_dirs)]
        maybe_sort(dirnames)
        maybe_sort(filenames)

        base = Path(dirpath)

        # Skip symlinked dirs when not following symlinks
        if not follow_symlinks and _is_symlink(base):
            continue

        for fn in filenames:
            p = base / fn

            # Skip symlinks unless explicitly allowed
            if not follow_symlinks and _is_symlink(p):
                continue

            # Only files
            try:
                if not p.is_file():
                    continue
            except OSError:
                continue

            try:
                rel = normalize_rel_path(str(p.relative_to(root)))
            except Exception:
                # If it can't be relativized, skip
                continue

            # Ignore patterns (scanner-level)
            if ignore_globs and any_glob_match(rel, ignore_globs):
                continue

            try:
                st = p.stat()
                size = int(st.st_size)
            except OSError:
                # unreadable -> still yield (engine will error during read)
                size = 0

            candidate = FileCandidate(
                abs_path=str(p),
                rel_path=rel,
                size_bytes=size,
                is_binary=is_probably_binary(p),
                extension=p.suffix.lower() or None,
            )
            yield candidate