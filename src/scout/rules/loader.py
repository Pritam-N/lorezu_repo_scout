from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from scout.core.models import Rule, RulePack, RuleSet
from scout.rules.validators import (
    RuleValidationError,
    build_ruleset,
    validate_rule_pack,
)
from scout.rules.schema_validate import validate_against_schema

import yaml
from importlib import resources as importlib_resources


DEFAULT_REPO_RULE_FILES = (
    ".secret-scout/rules.yaml",
    ".secret-scout/rules.yml",
)

DEFAULT_GLOBAL_RULE_FILES = (
    "~/.config/secret-scout/rules.yaml",
    "~/.config/secret-scout/rules.yml",
    "~/.secret-scout/rules.yaml",
    "~/.secret-scout/rules.yml",
)


@dataclass(frozen=True)
class LoadedRules:
    ruleset: RuleSet
    sources: List[str]


def _read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        return {}
    return data


def _read_builtin_yaml(builtin_name: str) -> Dict[str, Any]:
    pkg = "scout.rules.builtins"
    filename = f"{builtin_name}.yaml"
    with importlib_resources.files(pkg).joinpath(filename).open("rb") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {}
    return data


def find_repo_rules(start_dir: Path) -> Optional[Path]:
    cur = start_dir.resolve()
    for parent in [cur, *cur.parents]:
        for rel in DEFAULT_REPO_RULE_FILES:
            p = (parent / rel).resolve()
            if p.exists() and p.is_file():
                return p
    return None


def find_global_rules() -> Optional[Path]:
    for s in DEFAULT_GLOBAL_RULE_FILES:
        p = Path(s).expanduser().resolve()
        if p.exists() and p.is_file():
            return p
    return None


def _merge_rules_by_id(base: List[Rule], overrides: List[Rule]) -> List[Rule]:
    """Merge rules by id, override wins; stable order (base + new)."""
    out: Dict[str, Rule] = {r.id: r for r in base}
    order: List[str] = [r.id for r in base]

    for r in overrides:
        if r.id in out:
            out[r.id] = r
        else:
            out[r.id] = r
            order.append(r.id)

    return [out[rid] for rid in order]


def load_rule_pack_from_path(path: Path) -> RulePack:
    data = _read_yaml(path)
    # Handle empty rules section (YAML returns None for commented-out sections)
    if data.get("rules") is None:
        data["rules"] = []
    validate_against_schema(data, str(path))
    pack = RulePack.model_validate(data)
    pack.metadata.source = str(path)
    validate_rule_pack(pack)
    return pack


def load_builtin_rule_pack(name: str = "default") -> RulePack:
    data = _read_builtin_yaml(name)
    validate_against_schema(data, f"builtin:{name}")
    pack = RulePack.model_validate(data)
    pack.metadata.source = f"builtin:{name}"
    validate_rule_pack(pack)
    return pack


def load_ruleset(
    start_dir: Path,
    builtin: str = "default",
    extra_rule_files: Optional[List[Path]] = None,
) -> LoadedRules:
    """
    Precedence (lowest -> highest):
      builtin -> global -> repo -> extra_rule_files
    """
    extra_rule_files = extra_rule_files or []
    sources: List[str] = []
    packs: List[RulePack] = []

    # 1) builtin
    try:
        p = load_builtin_rule_pack(builtin)
        packs.append(p)
        sources.append(p.metadata.source or f"builtin:{builtin}")
    except RuleValidationError as e:
        raise typer.BadParameter(f"Builtin rule pack '{builtin}' invalid: {e}") from e

    # 2) global
    gp = find_global_rules()
    if gp:
        try:
            p = load_rule_pack_from_path(gp)
            packs.append(p)
            sources.append(p.metadata.source or str(gp))
        except RuleValidationError as e:
            raise typer.BadParameter(f"Global rules invalid at {gp}: {e}") from e

    # 3) repo
    rp = find_repo_rules(start_dir)
    if rp:
        try:
            p = load_rule_pack_from_path(rp)
            packs.append(p)
            sources.append(p.metadata.source or str(rp))
        except RuleValidationError as e:
            raise typer.BadParameter(f"Repo rules invalid at {rp}: {e}") from e

    # 4) extra files
    for path in extra_rule_files:
        ef = path.expanduser().resolve()
        if not ef.exists() or not ef.is_file():
            raise typer.BadParameter(f"Extra rule file not found: {ef}")
        try:
            p = load_rule_pack_from_path(ef)
            packs.append(p)
            sources.append(p.metadata.source or str(ef))
        except RuleValidationError as e:
            raise typer.BadParameter(f"Extra rules invalid at {ef}: {e}") from e

    # merge rules
    merged: List[Rule] = []
    for pack in packs:
        merged = _merge_rules_by_id(merged, pack.rules)

    # build final ruleset
    try:
        ruleset = build_ruleset(merged)
    except RuleValidationError as e:
        raise typer.BadParameter(f"Merged rules invalid: {e}") from e

    return LoadedRules(ruleset=ruleset, sources=sources)
