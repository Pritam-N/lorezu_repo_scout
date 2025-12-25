from __future__ import annotations

import fnmatch
import re
from functools import lru_cache
from typing import Iterable, Optional


def normalize_rel_path(rel_path: str) -> str:
    return (rel_path or "").replace("\\", "/")


def any_glob_match(rel_path: str, globs: Iterable[str]) -> bool:
    rp = normalize_rel_path(rel_path)
    for g in globs:
        if fnmatch.fnmatch(rp, g):
            return True
    return False


@lru_cache(maxsize=512)
def _compile_regex(pattern: str, flags: int) -> re.Pattern:
    return re.compile(pattern, flags)


def regex_search(pattern: str, text: str, *, flags: int = re.IGNORECASE) -> Optional[re.Match]:
    rx = _compile_regex(pattern, flags)
    return rx.search(text)


def regex_finditer(pattern: str, text: str, *, flags: int = re.IGNORECASE):
    rx = _compile_regex(pattern, flags)
    return rx.finditer(text)


def is_path_included(rel_path: str, include_globs: Iterable[str], exclude_globs: Iterable[str]) -> bool:
    """
    If include is empty => include everything (unless excluded).
    If include not empty => must match include and must not match exclude.
    """
    rp = normalize_rel_path(rel_path)
    inc = list(include_globs)
    exc = list(exclude_globs)

    if exc and any_glob_match(rp, exc):
        return False

    if not inc:
        return True

    return any_glob_match(rp, inc)