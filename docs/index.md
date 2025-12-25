# Secret Scout

Prevent accidental secret leaks by scanning repos for risky files and patterns.

## Features

- **Filename Detection** - Catch `.env`, private keys, and secrets folders
- **Content Scanning** - Regex patterns for AWS keys, GitHub tokens, passwords
- **Structured Parsing** - Understand dotenv, YAML, JSON, TOML, INI files
- **Baseline Support** - Suppress known findings for gradual adoption
- **GitHub Integration** - Scan entire orgs or user repos

## Quick Start

### Installation

```bash
pip install secret-scout
```

### Initialize a project

```bash
secret-scout init
```

This creates `.secret-scout/` with:

- `config.toml` - scan behavior settings
- `rules.yaml` - repo-specific rule overrides

### Scan a directory

```bash
# Scan current directory
secret-scout scan .

# Using --path option
secret-scout scan --path .

# Scan with verbose output
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

## Built-in Rules

Secret Scout includes rules for detecting:

| Category | Examples |
|----------|----------|
| **Filenames** | `.env`, `id_rsa`, `.pem`, `secrets/` |
| **AWS** | Access Key IDs (`AKIA...`) |
| **GitHub** | Personal access tokens (`ghp_...`) |
| **Generic** | `password=`, `api_key=`, `secret=` |
| **Structured** | Forbidden keys in dotenv files |

## Configuration

See [Configuration](configuration.md) for details on customizing scan behavior and rules.

## CLI Reference

See [CLI Reference](cli.md) for all available commands and options.

