# Architecture

> **secret-scout** — Prevent accidental secret leaks by scanning repos for risky files and patterns.

---

## Project Structure

```
secret-scout/
├── pyproject.toml          # Build config (hatchling), dependencies, entry points
├── README.md
├── LICENSE
├── CHANGELOG.md
├── mkdocs.yml              # Documentation site config
│
├── docs/
│   ├── index.md            # Landing page
│   ├── cli.md              # CLI reference
│   └── configuration.md    # Config & rules guide
│
├── src/scout/              # Main package (src layout)
│   ├── __init__.py
│   │
│   ├── cli/                # Command-line interface
│   │   ├── app.py          # Typer app + command registration
│   │   ├── commands/
│   │   │   ├── init.py         # `secret-scout init`
│   │   │   ├── scan_path.py    # `secret-scout scan`
│   │   │   ├── scan_github.py  # `secret-scout github`
│   │   │   ├── rules.py        # `secret-scout rules`
│   │   │   ├── baseline.py     # `secret-scout baseline`
│   │   │   └── config.py       # `secret-scout config`
│   │   └── ui/
│   │       ├── console.py      # Rich console wrappers, UIContext
│   │       ├── formatters.py   # Text/JSON/SARIF renderers
│   │       ├── progress.py     # Progress bars
│   │       └── tui.py          # Interactive terminal UI (Textual)
│   │
│   ├── core/               # Domain logic
│   │   ├── models.py       # Finding, Rule, ScanTarget, ScanResult, RuleSet
│   │   ├── config.py       # Pydantic config models + loaders
│   │   ├── engine.py       # Orchestrates scanning flow
│   │   ├── policy.py       # Rule evaluation pipeline
│   │   ├── matcher.py      # Filename/content matching (glob, regex)
│   │   ├── baseline.py     # Baseline load/apply logic
│   │   ├── redaction.py    # Redact/truncate sensitive output
│   │   └── errors.py       # Typed exceptions + exit codes
│   │
│   ├── rules/              # Rule system
│   │   ├── builtins/
│   │   │   ├── default.yaml    # Default rule pack
│   │   │   └── strict.yaml     # Stricter rule pack
│   │   ├── schema.json         # JSON Schema for rule validation
│   │   ├── schema_validate.py  # Schema validation helpers
│   │   ├── loader.py           # Load/merge rule packs
│   │   └── validators.py       # Semantic rule validation
│   │
│   ├── scanners/           # Input sources
│   │   ├── fs_scanner.py       # Filesystem traversal
│   │   ├── git_scanner.py      # Git repo scanning (tracked/untracked)
│   │   └── github/
│   │       ├── api.py          # GitHub API client
│   │       ├── clone.py        # Clone manager, temp dirs
│   │       ├── filters.py      # Repo include/exclude filters
│   │       └── scan.py         # Orchestrate GitHub org/user scans
│   │
│   ├── parsers/            # Structured file parsers
│   │   ├── dotenv_parser.py
│   │   ├── yaml_parser.py
│   │   ├── json_parser.py
│   │   ├── toml_parser.py
│   │   └── ini_parser.py
│   │
│   └── utils/              # Shared utilities
│       ├── paths.py            # Path manipulation helpers
│       ├── hashing.py          # Content hashes for caching/baseline
│       ├── concurrency.py      # Thread/async helpers
│       └── logging.py          # Logging setup
│
└── tests/
    ├── test_cli.py
    └── fixtures/
```

---

## Core Concepts

### Data Models

| Model | Description |
|-------|-------------|
| `Rule` | A single detection rule (filename, regex, or structured) |
| `RuleSet` | Validated collection of enabled rules |
| `RulePack` | YAML file containing rules + metadata |
| `ScanTarget` | What we're scanning (local path, GitHub repo) |
| `FileCandidate` | A file to be evaluated |
| `Finding` | A detected secret/risk with location + context |
| `ScanResult` | Aggregate of findings, errors, stats |
| `ScanConfig` | Runtime configuration (skip dirs, redact, etc.) |

### Rule Types

| Type | Matches On | Example Use Case |
|------|------------|------------------|
| `filename` | Glob patterns against file paths | `*.pem`, `.env*`, `id_rsa` |
| `regex` | Regular expressions against content | API keys, tokens, passwords |
| `structured` | Key names in parsed config files | Forbidden keys like `password`, `secret` |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI Layer                                  │
│  secret-scout scan . --verbose                                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Configuration                                 │
│  1. Load defaults                                                    │
│  2. Merge global config (~/.config/secret-scout/config.toml)        │
│  3. Merge repo config (.secret-scout/config.toml)                   │
│  4. Apply CLI overrides                                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Rule Loading                                 │
│  1. Load builtin pack (default.yaml or strict.yaml)                 │
│  2. Merge global rules (~/.config/secret-scout/rules.yaml)          │
│  3. Merge repo rules (.secret-scout/rules.yaml)                     │
│  4. Merge --rules CLI files (highest precedence)                    │
│  5. Validate + compile regexes                                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Scanning                                    │
│  Scanner (git or fs) enumerates FileCandidate objects               │
│  - Respects .gitignore, skip_dirs, max_file_bytes                   │
│  - Filters binary files                                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Evaluation                                   │
│  For each candidate:                                                 │
│  1. Apply filename rules (glob matching)                            │
│  2. Read content (with size/encoding guards)                        │
│  3. Apply regex rules (pattern matching)                            │
│  4. Parse structured files → apply structured rules                 │
│  5. Generate Finding objects with redacted samples                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Baseline Filtering                              │
│  If baseline exists:                                                 │
│  - Filter out findings matching baseline hashes                     │
│  - Report only new findings                                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Output                                      │
│  - TUI (interactive terminal) for humans                            │
│  - Rich tables (--plain) for CI logs                                │
│  - JSON (--json) for machine consumption                            │
│  - SARIF for GitHub Security integration                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Rule Merging Strategy

Rules are merged by `id`. Later sources override earlier ones:

```
builtin (default.yaml)
    ↓ override by id
global (~/.config/secret-scout/rules.yaml)
    ↓ override by id
repo (.secret-scout/rules.yaml)
    ↓ override by id
CLI (--rules extra.yaml)
```

To **disable** a builtin rule in your repo:

```yaml
rules:
  - id: private-key-file
    enabled: false
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No findings (clean) |
| `1` | Findings detected |
| `2` | Execution error (config, IO, etc.) |

---

## Key Design Decisions

1. **src layout** — Package lives in `src/scout/` for clean imports and proper editable installs.

2. **Pydantic models** — All config and data models use Pydantic v2 for validation and serialization.

3. **Rule packs as YAML** — Human-readable, easy to extend, validated against JSON Schema.

4. **Layered config** — Defaults → global → repo → CLI allows org-wide policies with local overrides.

5. **Git-aware scanning** — Respects `.gitignore` by default; option to include ignored files.

6. **Redaction by default** — Never print full secrets in output; show truncated/redacted samples.

7. **TUI for humans, plain for CI** — Auto-detect terminal; use `--plain` or `--json` in pipelines.

8. **Baseline for adoption** — Acknowledge existing findings; only fail on new ones.

---

## Build Order (for contributors)

| Phase | Components |
|-------|------------|
| 1. Rules | `schema.json`, `builtins/*.yaml`, `loader.py`, `validators.py` |
| 2. Core | `errors.py`, `models.py`, `config.py`, `matcher.py`, `policy.py`, `engine.py` |
| 3. Scanners | `fs_scanner.py`, `git_scanner.py` |
| 4. Parsers | `dotenv_parser.py`, `yaml_parser.py`, `json_parser.py`, etc. |
| 5. Baseline | `core/baseline.py` |
| 6. UI | `formatters.py`, `console.py`, `tui.py` |
| 7. CLI | `app.py`, `commands/*.py` |
| 8. GitHub | `scanners/github/*.py` |
| 9. Hardening | Tests, CI, docs |

---

## Related Files

- **README.md** — User-facing quick start
- **docs/** — Full documentation (MkDocs)
- **pyproject.toml** — Package metadata and dependencies
