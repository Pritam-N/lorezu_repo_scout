# CLI Reference

## Commands

### `secret-scout init`

Initialize secret-scout configuration in a repository.

```bash
secret-scout init [DIRECTORY] [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `DIRECTORY` | Target directory (repo root) | `.` |

**Options:**

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing files |
| `--strict` | Generate stricter starter rules template |
| `--no-gitignore` | Don't create `.secret-scout/.gitignore` |
| `--no-readme` | Don't create `.secret-scout/README.md` |

---

### `secret-scout scan`

Scan a local directory for secrets.

```bash
secret-scout scan [PATH] [OPTIONS]
secret-scout scan --path PATH [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Directory to scan (positional) | `.` (current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `--path`, `-p` | Directory to scan (alternative to positional arg) |
| `--verbose` | Show detailed output |
| `--fail / --no-fail` | Exit with non-zero code if findings exist (default: true) |
| `--plain` | Disable TUI; print Rich output (CI-friendly) |
| `--builtin` | Built-in rule pack to use (default: `default`) |
| `--rules` | Additional rules file(s) to load (repeatable) |
| `--ignore` | Glob patterns to ignore (repeatable) |
| `--include-ignored / --no-include-ignored` | Include git-ignored files |
| `--include-untracked / --no-include-untracked` | Include untracked files (default: true) |
| `--ignore-errors` | Continue on file read errors |

---

### `secret-scout github`

Scan GitHub repositories for secrets.

```bash
secret-scout github [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--org` | GitHub organization to scan |
| `--user` | GitHub user to scan |
| `--token` | GitHub personal access token (or set `GITHUB_TOKEN`) |
| `--include` | Regex pattern to include repos |
| `--exclude` | Regex pattern to exclude repos |
| `--archived` | Include archived repos |
| `--forks` | Include forked repos |
| `--private` | Include private repos |
| `--verbose` | Show detailed output |
| `--fail` | Exit with non-zero code if findings exist |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success, no findings (or `--fail` not set) |
| `1` | Findings detected (when `--fail` is set) |
| `2` | Configuration or rule error |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub personal access token for API access |
| `SECRET_SCOUT_CONFIG` | Path to global config file |

