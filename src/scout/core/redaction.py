from __future__ import annotations

import hashlib


def redact_value(value: str, *, keep: int = 4) -> str:
    """
    Redact a potentially sensitive match so it is safe to print in logs.
    Example: "abcd...wxyz"
    """
    v = (value or "").strip()
    if not v:
        return "***REDACTED***"
    if len(v) <= (keep * 2 + 2):
        return "***REDACTED***"
    return f"{v[:keep]}…{v[-keep:]}"


def truncate(value: str, *, max_len: int = 160) -> str:
    v = value or ""
    if len(v) <= max_len:
        return v
    return v[:max_len] + "…"


def stable_hash(
    *parts: str,
    algo: str = "sha256",
    max_len: int = 24,
) -> str:
    """
    Create a stable short hash for baselines/deduping without storing secrets.
    """
    h = hashlib.new(algo)
    joined = "\n".join(parts)
    h.update(joined.encode("utf-8", errors="replace"))
    return h.hexdigest()[:max_len]