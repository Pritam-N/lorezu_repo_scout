from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

from scout.core.matcher import any_glob_match, is_path_included, normalize_rel_path, regex_finditer, regex_search
from scout.core.models import (
    FileCandidate,
    Finding,
    FindingKind,
    MatchScope,
    Rule,
    RuleSet,
    RuleType,
    ScanConfig,
    ValuePolicy,
)
from scout.core.redaction import redact_value, stable_hash, truncate

TextReader = Callable[[FileCandidate], Optional[str]]
StructuredParser = Callable[[str], dict]


def evaluate_file(
    *,
    target_name: str,
    candidate: FileCandidate,
    ruleset: RuleSet,
    config: ScanConfig,
    read_text: TextReader,
    structured_parsers: Optional[Dict[str, StructuredParser]] = None,
) -> List[Finding]:
    """
    Evaluate a single file candidate against enabled rules.

    Notes:
    - Never returns raw secrets if config.redact=True.
    - Always attaches match_hash for baselines/deduping.
    """
    findings: List[Finding] = []
    rel = normalize_rel_path(candidate.rel_path)

    for rule in ruleset.enabled():
        # include/exclude filters
        if not is_path_included(rel, rule.include, rule.exclude):
            continue

        # allow-path suppressions
        if rule.allow_paths and any_glob_match(rel, rule.allow_paths):
            continue

        if rule.type == RuleType.FILENAME:
            findings.extend(_eval_filename_rule(target_name, rel, rule))

        elif rule.type == RuleType.REGEX:
            text = read_text(candidate)
            if not text:
                continue
            findings.extend(_eval_regex_rule(target_name, rel, rule, text, redact=config.redact))

        elif rule.type == RuleType.STRUCTURED:
            if not rule.structured or not structured_parsers:
                continue
            fmt = rule.structured.format.value
            parser = structured_parsers.get(fmt)
            if parser is None:
                continue

            text = read_text(candidate)
            if not text:
                continue
            findings.extend(_eval_structured_rule(target_name, rel, rule, text, parser, redact=config.redact))

    return findings


def _eval_filename_rule(target: str, rel_path: str, rule: Rule) -> List[Finding]:
    assert rule.filename is not None

    if rule.filename.pattern_type == "glob":
        matched = any_glob_match(rel_path, [rule.filename.pattern])
    else:
        matched = regex_search(rule.filename.pattern, rel_path) is not None

    if not matched:
        return []

    return [
        Finding(
            target=target,
            file=rel_path,
            kind=FindingKind.FILENAME,
            rule_id=rule.id,
            severity=rule.severity,
            message=rule.description or "Suspicious filename detected",
            match_hash=stable_hash(rule.id, rel_path, "filename"),
        )
    ]


def _allow_regex_suppresses(rule: Rule, text: str) -> bool:
    if not rule.allow_regexes:
        return False
    for arx in rule.allow_regexes:
        try:
            if re.search(arx, text, flags=re.IGNORECASE):
                return True
        except re.error:
            # allowlist regex should already be validated; ignore safely
            continue
    return False


def _safe_sample(sample: str, *, redact: bool) -> str:
    s = truncate(sample.strip(), max_len=160)
    return redact_value(s) if redact else s


def _eval_regex_rule(target: str, rel_path: str, rule: Rule, text: str, *, redact: bool) -> List[Finding]:
    assert rule.regex is not None

    flags = re.IGNORECASE
    if rule.regex.multiline:
        flags |= re.MULTILINE | re.DOTALL

    out: List[Finding] = []

    # FILE scope: one finding per match (up to max_matches), no line numbers
    if rule.regex.scope == MatchScope.FILE:
        count = 0
        for m in regex_finditer(rule.regex.regex, text, flags=flags):
            raw = m.group(0)
            if _allow_regex_suppresses(rule, raw):
                continue

            out.append(
                Finding(
                    target=target,
                    file=rel_path,
                    kind=FindingKind.CONTENT,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description or "Secret-like pattern detected",
                    sample=_safe_sample(raw, redact=redact),
                    match_hash=stable_hash(rule.id, rel_path, "content", "file", raw),
                )
            )
            count += 1
            if count >= rule.regex.max_matches:
                break

        return out

    # LINE scope: find matches per line (better diagnostics)
    count = 0
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line or len(line) < 4:
            continue

        # allowlist can suppress whole line
        if _allow_regex_suppresses(rule, line):
            continue

        for m in regex_finditer(rule.regex.regex, line, flags=flags):
            raw = m.group(0)
            if _allow_regex_suppresses(rule, raw):
                continue

            out.append(
                Finding(
                    target=target,
                    file=rel_path,
                    kind=FindingKind.CONTENT,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description or "Secret-like pattern detected",
                    line=idx,
                    sample=_safe_sample(raw, redact=redact),
                    match_hash=stable_hash(rule.id, rel_path, "content", str(idx), raw),
                )
            )
            count += 1
            if count >= rule.regex.max_matches:
                return out

    return out


def _looks_plaintext_secret(v: str) -> bool:
    """
    Heuristic: long-ish token with entropy-like charset and not obviously a reference.
    """
    s = (v or "").strip()
    if not s:
        return False
    if s.startswith("${") or s.startswith("$") or s.startswith("vault://"):
        return False
    if len(s) < 12:
        return False
    # contains at least one letter and one digit/symbol-ish
    has_alpha = any(c.isalpha() for c in s)
    has_other = any(c.isdigit() or c in "_-+/=." for c in s)
    return has_alpha and has_other


def _value_violates_policy(policy: ValuePolicy, value: object) -> bool:
    """
    Returns True if the key/value should be flagged under this policy.
    """
    if policy == ValuePolicy.ANY:
        return True

    s = "" if value is None else str(value).strip()

    if policy == ValuePolicy.NON_EMPTY:
        return bool(s)

    if policy == ValuePolicy.MUST_REFERENCE_ENV:
        # allow $VAR or ${VAR}
        return not (s.startswith("$") or s.startswith("${"))

    if policy == ValuePolicy.MUST_REFERENCE_VAULT:
        return not s.startswith("vault://")

    if policy == ValuePolicy.PLAINTEXT:
        return _looks_plaintext_secret(s)

    # default: be conservative
    return True


def _eval_structured_rule(
    target: str,
    rel_path: str,
    rule: Rule,
    text: str,
    parser: StructuredParser,
    *,
    redact: bool,
) -> List[Finding]:
    """
    Parse file into dict-like object and apply forbidden/allowed key policy.
    """
    assert rule.structured is not None
    cfg = rule.structured

    try:
        data = parser(text) or {}
    except Exception:
        # Parsing failures should not kill scans
        return []

    if not isinstance(data, dict):
        return []

    def norm(k: str) -> str:
        return k.upper() if cfg.case_insensitive_keys else k

    forbidden = {norm(k) for k in cfg.forbidden_keys}
    allowed = {norm(k) for k in cfg.allowed_keys} if cfg.allowed_keys else set()

    out: List[Finding] = []
    for k, v in data.items():
        key = str(k)
        nk = norm(key)

        if allowed and nk in allowed:
            continue
        if forbidden and nk not in forbidden:
            continue

        # Apply value policy
        if not _value_violates_policy(cfg.value_policy, v):
            continue

        hint = None
        if v is not None:
            hint = _safe_sample(str(v), redact=redact)

        out.append(
            Finding(
                target=target,
                file=rel_path,
                kind=FindingKind.STRUCTURED,
                rule_id=rule.id,
                severity=rule.severity,
                message=rule.description or "Forbidden key detected",
                key=key,
                value_hint=hint,
                match_hash=stable_hash(rule.id, rel_path, "structured", key, str(v)),
            )
        )

    return out