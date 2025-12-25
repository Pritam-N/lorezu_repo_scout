from __future__ import annotations

from ast import Tuple
import re
from typing import Any, Dict, Iterable, List, Optional, Union

from scout.core.models import Rule, RulePack, RuleSet, RuleType


class RuleValidationError(ValueError):
    pass


def validate_rule_pack(rule_pack: RulePack) -> None:
    """Validate and sanity check a rule pack."""
    validate_rules(rule_pack.rules)


def validate_rules(rules: Iterable[Rule]) -> None:
    """validate rules and ensure regexes are valid."""
    rules_list = list(rules)
    _ensure_unique_ids(rules_list)

    for r in rules_list:
        if not r.enabled:
            continue

        # Validate include/exclude globs are strings (Pydantic already ensures)
        # Validate allow_regexes compile (if provided)
        for arx in r.allow_regexes:
            _compile_regex(arx, context=f"{r.id}.allow_regexes")

        if r.type == RuleType.FILENAME:
            assert r.filename is not None
            if r.filename.pattern_type == "regex":
                _compile_regex(r.filename.pattern, context=f"{r.id}.filename.pattern")

        elif r.type == RuleType.REGEX:
            assert r.regex is not None
            flags = re.IGNORECASE
            if r.regex.multiline:
                flags |= re.MULTILINE | re.DOTALL
            _compile_regex(r.regex.regex, context=f"{r.id}.regex.regex", flags=flags)

        # Nothing to compile; parsers will validate data later.
        # But we can sanity-check forbidden/allowed keys are not overlapping.
        elif r.type == RuleType.STRUCTURED:
            assert r.structured is not None
            fk = set(
                _norm_keys(
                    r.structured.forbidden_keys, r.structured.case_insensitive_keys
                )
            )
            ak = set(
                _norm_keys(
                    r.structured.allowed_keys, r.structured.case_insensitive_keys
                )
            )
            overlap = fk.intersection(ak)
            if overlap:
                raise RuleValidationError(
                    f"Rule '{r.id}' has keys present in both forbidden_keys and allowed_keys: {sorted(overlap)}"
                )

        else:
            raise RuleValidationError(f"Unknown rule type: {r.type}")


def build_ruleset(rules: List[Rule]) -> RuleSet:
    """Validate and return a RuleSet from a list of rules."""
    validate_rules(rules)
    # keep only enabled rules
    enabled_rules = [r for r in rules if r.enabled]
    # sort by severity descending
    enabled_rules.sort(key=lambda r: r.severity, reverse=True)
    # deduplicate by id (keep first occurrence after sort)
    seen_ids: set[str] = set()
    deduped: List[Rule] = []
    for r in enabled_rules:
        if r.id not in seen_ids:
            seen_ids.add(r.id)
            deduped.append(r)
    return RuleSet(rules=deduped)


def _ensure_unique_ids(rules: List[Rule]) -> None:
    seen = set()
    dups = []
    for r in rules:
        if r.id in seen:
            dups.append(r.id)
        seen.add(r.id)
    if dups:
        raise RuleValidationError(f"Duplicate rule IDs: {sorted(dups)}")


def _compile_regex(
    pattern: str, context: str, flags: int = re.IGNORECASE
) -> Tuple[str, re.Pattern]:
    try:
        return pattern, re.compile(pattern, flags)
    except re.error as e:
        raise RuleValidationError(f"Invalid regex in {context}: {e}") from e


def _norm_keys(keys: List[str], case_insensitive: bool = True) -> List[str]:
    if not case_insensitive:
        return keys
    return [k.upper() for k in keys]
