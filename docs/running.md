repo-scout/
  pyproject.toml
  README.md
  LICENSE
  CHANGELOG.md

  secret_scout/
    __init__.py

    cli/
      __init__.py
      app.py              # Typer app + command registration
      commands/
        __init__.py
        init.py
        scan_path.py
        scan_github.py
        rules.py
        baseline.py
        config.py
      ui/
        __init__.py
        console.py         # rich console wrappers
        formatters.py      # text/json/sarif renderers

    core/
      __init__.py
      engine.py            # orchestrates scanning flow
      models.py            # Finding, Rule, RepoTarget, ScanResult
      config.py            # pydantic config models + loaders
      policy.py            # rule evaluation pipeline
      matcher.py           # filename/content matching logic
      baseline.py          # baseline load/apply logic
      redaction.py         # redact/truncate rules
      errors.py            # typed exceptions + exit codes

    rules/
      __init__.py
      builtins/
        default.yaml       # built-in rule pack
        strict.yaml        # optional stricter pack
      schema.json          # rule schema for validation
      loader.py            # load/merge rule packs
      validators.py        # semantic validations

    scanners/
      __init__.py
      fs_scanner.py        # filesystem traversal, ignore handling
      git_scanner.py       # tracked/untracked, optionally include-ignored
      github/
        __init__.py
        api.py             # list repos, pagination, rate limit
        clone.py           # clone manager, temp dirs, retries
        filters.py         # include/exclude rules

    parsers/
      __init__.py
      dotenv_parser.py
      yaml_parser.py
      json_parser.py
      toml_parser.py
      ini_parser.py

    utils/
      __init__.py
      paths.py
      hashing.py           # optional content hashes for caching
      concurrency.py       # thread/async helpers
      logging.py

  tests/
    test_rules_loader.py
    test_engine.py
    test_git_scanner.py
    test_fs_scanner.py
    fixtures/

  .github/workflows/
    ci.yml



Build in this order:
	1.	Rules subsystem (foundation)

	•	rules/schema.json
	•	rules/builtins/default.yaml (+ optional strict.yaml)
	•	rules/loader.py (load + merge packs: builtin → global → repo → CLI)
	•	rules/validators.py (compile regex, validate per rule type)

	2.	Core engine skeleton

	•	core/errors.py (exit codes + typed exceptions)
	•	core/redaction.py (safe sample redaction/truncation + optional hashing)
	•	core/matcher.py (glob + regex helpers, allowlists)
	•	core/policy.py (evaluate one file against rules)
	•	core/engine.py (orchestrate: enumerate files → evaluate → baseline → result)

	3.	Scanners (inputs)

	•	scanners/fs_scanner.py (walk dir, skip dirs, ignore globs, binary + size filters)
	•	scanners/git_scanner.py (tracked + untracked + optionally ignored)

	4.	Format parsers (only after engine works for regex/filename)

	•	parsers/dotenv_parser.py (dotenv key/value)
	•	parsers/yaml_parser.py, json_parser.py, toml_parser.py, ini_parser.py

	5.	Baseline support (adoption feature)

	•	core/baseline.py (create/apply, match via match_hash)

	6.	Outputs / reporting

	•	cli/ui/formatters.py: text, json, then sarif
	•	cli/ui/console.py (rich output, CI-safe mode)

	7.	CLI commands wiring (thin layer)

	•	cli/app.py register commands
	•	cli/commands/init.py
	•	cli/commands/scan_path.py
	•	cli/commands/scan_github.py (after GitHub scanner exists)
	•	cli/commands/rules.py, baseline.py

	8.	GitHub scanning module

	•	scanners/github/api.py (list repos, pagination, rate limits)
	•	scanners/github/clone.py (temp dir manager, retries)
	•	scanners/github/filters.py

	9.	Hardening

	•	unit tests + fixtures
	•	pre-commit / GitHub Actions examples
	•	docs

