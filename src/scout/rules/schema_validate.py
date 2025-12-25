from __future__ import annotations

import json
from typing import Any, Dict

import typer

try:
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore

from importlib import resources as importlib_resources


def _load_schema() -> Dict[str, Any]:
    """
    Load schema.json packaged in scout.rules.
    """
    with importlib_resources.files("scout.rules").joinpath("schema.json").open("rb") as f:
        return json.load(f)


def validate_against_schema(data: Dict[str, Any], source: str) -> None:
    """
    Validate raw rule-pack dict (from YAML) against schema.json.
    Raises typer.BadParameter with a helpful message on failure.
    """
    if jsonschema is None:
        # Optional dependency; don't hard-fail
        return

    schema = _load_schema()
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        # Show the path inside the document where validation failed
        path = ".".join(str(p) for p in e.path) if e.path else "<root>"
        msg = f"Rule pack schema validation failed at {path}: {e.message} (source: {source})"
        raise typer.BadParameter(msg) from e