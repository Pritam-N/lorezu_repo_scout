# Secret Scout

> Prevent accidental secret leaks by scanning repos for risky files and patterns.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Local & Remote Scanning** - Scan local directories or entire GitHub orgs/users
- **Filename Detection** - Catch `.env`, private keys, secrets folders
- **Content Scanning** - Regex patterns for AWS keys, GitHub tokens, passwords
- **Structured Parsing** - Understand dotenv, YAML, JSON, TOML, INI files
- **Baseline Support** - Suppress known findings for gradual adoption
- **CI-Ready** - Deterministic output, SARIF export, proper exit codes

## Quick Start

### Installation

```bash
pip install secret-scout
```

### Initialize a project

```bash
secret-scout init
```

Creates `.secret-scout/` with:
- `config.toml` - scan behavior settings
- `rules.yaml` - repo-specific rule overrides

### Scan a directory

```bash
# Scan current directory
secret-scout scan .

# Using --path option
secret-scout scan --path .

# Verbose output
secret-scout scan . --verbose

# Fail on findings (for CI)
secret-scout scan . --fail
```

### Scan GitHub repos

```bash
# Scan all repos in an org
secret-scout github --org my-org --token $GITHUB_TOKEN

# Scan a user's repos
secret-scout github --user octocat --token $GITHUB_TOKEN
```

---

## Feature Plan

### 1. Core Scanning Modes

| Mode | Description |
|------|-------------|
| **Local path scan** | Scan a folder (repo or non-repo). If repo: scan tracked + untracked + modified. Optional `--include-ignored` to catch `.env` files that are ignored but present. |
| **Workspace scan** | Discover all nested git repos under a path and scan each. |
| **GitHub account scan** | `--org` or `--user`. List repos via API, clone to temp, scan with concurrency. |
| **CI mode** | Deterministic output. Exit codes: `0` = clean, `1` = findings, `2` = tool/config error. |

### 2. Rules and Extensibility

The heart of the tool. Rules act as a policy engine.

#### Rule Types

| Type | Description | Examples |
|------|-------------|----------|
| **Filename** | Detect forbidden/suspicious files by path/name | `.env`, `*.pem`, `id_rsa`, `secrets.*` |
| **Content regex** | Detect secret-like patterns in text files | `AKIA...`, `BEGIN PRIVATE KEY`, `PASSWORD=...` |
| **Structured** | Parse files and evaluate keys/values | dotenv, YAML, JSON, TOML/INI |

#### Structured Rule Examples

- Forbid keys: `AWS_SECRET_ACCESS_KEY`, `OPENAI_API_KEY`
- Allowlist certain keys in `example.env`
- Enforce "no plaintext secrets" unless value is `${VAR}` or `vault://...`

#### Rule Packs

- **Built-in pack**: `default` (safe baseline)
- **User packs** loaded from:
  - Repo config: `.secret-scout/`
  - Global config: `~/.config/secret-scout/`
- **Formats**:
  - `rules.yaml` (non-dev friendly)
  - Optional Python plugin packs (enterprise teams)

#### Rule Controls

- `severity`: `low` | `medium` | `high` | `critical`
- `tags`: `aws`, `github`, `private-key`, `password`
- Per-rule allowlist:
  - Path allowlist globs
  - Regex allowlist on matches (reduce false positives)

### 3. Output and Reporting

| Format | Use Case |
|--------|----------|
| **Human** | Rich terminal output + plain text for CI logs |
| **JSON** | Machine-readable findings |
| **SARIF** | GitHub code scanning integration |
| **JUnit** | CI test-style reporting (optional) |

Redaction is **on by default**. Use `--no-redact` only for local debugging.

### 4. Baseline + Suppressions

For real-world adoption:

```bash
# Capture current findings
secret-scout baseline create

# Suppress known findings
secret-scout baseline apply
```

**"New findings only"** mode for CI: blocks only regressions while teams clean up gradually.

### 5. Performance + Safety

- Skip binary and large files (configurable `--max-bytes`)
- Fast path filters (by extension, ignore globs)
- Deterministic traversal ordering (stable output)
- Never print full secrets; redact + truncate
- Safe temp handling (permissions, auto-clean)

### 6. Commands

| Command | Description |
|---------|-------------|
| `secret-scout init` | Generate `.secret-scout/config.toml` + starter rule pack + ignore file |
| `secret-scout scan [PATH]` | Scan local path. Options: `--path`, `--include-ignored`, `--format`, `--fail` |
| `secret-scout scan github` | Scan GitHub org/user. Options: filters, `--workers`, `--keep-temp`, `--format`, `--fail` |
| `secret-scout rules list\|show\|validate\|test` | Manage and test rules |
| `secret-scout baseline create\|apply` | Manage baselines |
| `secret-scout config validate\|print` | Validate and inspect configuration |

---

## Project Structure

```
secret-scout/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
│
├── src/scout/
│   ├── __init__.py
│   │
│   ├── cli/                    # Command-line interface
│   │   ├── app.py              # Typer app + command registration
│   │   ├── commands/
│   │   │   ├── init.py
│   │   │   ├── scan_path.py
│   │   │   ├── scan_github.py
│   │   │   ├── rules.py
│   │   │   ├── baseline.py
│   │   │   └── config.py
│   │   └── ui/
│   │       ├── console.py      # Rich console wrappers
│   │       └── formatters.py   # text/json/sarif renderers
│   │
│   ├── core/                   # Business logic (no CLI/UI coupling)
│   │   ├── engine.py           # Orchestrates scanning flow
│   │   ├── models.py           # Finding, Rule, RepoTarget, ScanResult
│   │   ├── config.py           # Pydantic config models + loaders
│   │   ├── policy.py           # Rule evaluation pipeline
│   │   ├── matcher.py          # Filename/content matching logic
│   │   ├── baseline.py         # Baseline load/apply logic
│   │   ├── redaction.py        # Redact/truncate rules
│   │   └── errors.py           # Typed exceptions + exit codes
│   │
│   ├── rules/                  # Rule subsystem
│   │   ├── builtins/
│   │   │   ├── default.yaml    # Built-in rule pack
│   │   │   └── strict.yaml     # Optional stricter pack
│   │   ├── schema.json         # Rule schema for validation
│   │   ├── loader.py           # Load/merge rule packs
│   │   └── validators.py       # Semantic validations
│   │
│   ├── scanners/               # Input adapters
│   │   ├── fs_scanner.py       # Filesystem traversal
│   │   ├── git_scanner.py      # Tracked/untracked files
│   │   └── github/
│   │       ├── api.py          # List repos, pagination, rate limits
│   │       ├── clone.py        # Clone manager, temp dirs, retries
│   │       └── filters.py      # Include/exclude rules
│   │
│   ├── parsers/                # File format parsers
│   │   ├── dotenv_parser.py
│   │   ├── yaml_parser.py
│   │   ├── json_parser.py
│   │   ├── toml_parser.py
│   │   └── ini_parser.py
│   │
│   └── utils/
│       ├── paths.py
│       ├── hashing.py          # Content hashes for caching
│       ├── concurrency.py      # Thread/async helpers
│       └── logging.py
│
└── tests/
    ├── test_rules_loader.py
    ├── test_engine.py
    ├── test_git_scanner.py
    ├── test_fs_scanner.py
    └── fixtures/
```

### Why This Structure Works

- **`core/`** is pure business logic (testable, no Typer/Rich/GitHub coupling)
- **`scanners/`** are adapters (FS/Git/GitHub)
- **`rules/`** is a standalone subsystem (loading, merging, validating)
- **`parsers/`** lets you add file-format specific logic cleanly
- **`cli/`** stays thin: parse args → call `core.engine`

---

## Architecture

### Data Contracts

| Model | Description |
|-------|-------------|
| `Rule` | id, type, severity, target globs, regex, format, allowlists |
| `Finding` | repo/target, file, kind, rule_id, line, sample_redacted |
| `ScanTarget` | Local path OR GitHub repo clone path |
| `ScanResult` | findings, stats, duration, errors |

### Scanning Pipeline

```
1. Enumerate files (FS/Git/GitHub clone)
2. Apply ignore globs + size/binary filters
3. Apply filename rules
4. Choose evaluator:
   ├── Regex content evaluator
   └── Structured evaluator (dotenv/yaml/json...)
5. Emit findings
6. Apply baseline suppression
7. Render output + choose exit code
```

### Rule Merge Order

1. Built-in defaults (lowest priority)
2. Org/global pack
3. Repo pack
4. CLI-provided rules (highest priority)

### CI First-Class

- Stable output ordering
- SARIF export for GitHub code scanning
- Redaction on by default
- `--fail` default true in CI (detectable via `CI=true` env)

---

## License

MIT
