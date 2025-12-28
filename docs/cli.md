# CLI Reference

## Commands

### `scout init repo`

Initialize scout configuration in a repository.

```bash
scout init repo [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Target directory (repo root) | `.` |

**Options:**

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing files |

---

### `scout scan path`

Scan a local directory for secrets.

```bash
scout scan path [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Directory to scan | `.` (current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed output |
| `--fail / --no-fail` | Exit with non-zero code if findings exist (default: `--fail`) |
| `--plain` | Disable TUI; print Rich output (CI-friendly) |
| `--builtin NAME` | Built-in rule pack to use: `default` or `strict` (default: `default`) |
| `--rules FILE` | Additional rules file(s) to load (repeatable) |
| `--ignore GLOB` | Glob patterns to ignore (repeatable) |
| `--include-ignored / --no-include-ignored` | Include git-ignored files (overrides config) |
| `--include-untracked / --no-include-untracked` | Include untracked files (default: true) |
| `--ignore-errors` | Continue on file read errors |

---

### `scout github`

Scan GitHub repositories for secrets.

```bash
scout github [OPTIONS]
```

**Required Options:**

| Option | Description |
|--------|-------------|
| `--org ORG` | GitHub organization to scan (required if `--user` not provided) |
| `--user USER` | GitHub user to scan (required if `--org` not provided) |

**Options:**

| Option | Description |
|--------|-------------|
| `--token TOKEN` | GitHub personal access token (or set `GITHUB_TOKEN` env var) |
| `--include GLOB` | Glob pattern to include repos by full_name (repeatable) |
| `--exclude GLOB` | Glob pattern to exclude repos by full_name (repeatable) |
| `--repo REPO` | Explicit repo allowlist, format: `org/repo` (repeatable) |
| `--include-archived` | Include archived repos (default: false) |
| `--include-forks` | Include forked repos (default: false) |
| `--include-private / --no-include-private` | Include private repos (default: true) |
| `--max-repos N` | Limit number of repos to scan |
| `--concurrency N` | Number of parallel workers (1-32, default: 4) |
| `--shallow / --no-shallow` | Use shallow clones (default: true) |
| `--blobless / --no-blobless` | Use blobless clones (default: true) |
| `--tmp-dir PATH` | Custom workspace directory (default: temp dir) |
| `--keep-clones` | Don't delete workspace after scanning |
| `--ignore GLOB` | Ignore paths within repos (repeatable) |
| `--builtin NAME` | Builtin rule pack (default: `default`) |
| `--rules FILE` | Extra rule files (repeatable) |
| `--plain` | Disable TUI (CI-friendly) |
| `--fail / --no-fail` | Exit 1 on findings (default: `--fail`) |
| `--ignore-errors` | Don't exit on repo errors |
| `--verbose` | Show scan summary |

---

### `scout rules validate`

Validate rule files.

```bash
scout rules validate [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Path to resolve repo/global rules from | `.` |

**Options:**

| Option | Description |
|--------|-------------|
| `--builtin NAME` | Builtin pack to use (default: `default`) |
| `--rules FILE` | Extra rule packs (repeatable) |

---

### `scout baseline gen`

Generate baseline from current findings (coming soon).

```bash
scout baseline gen
```

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
| `SCOUT_EDITOR`, `VISUAL`, `EDITOR` | Preferred editor for opening findings (first match wins) |

