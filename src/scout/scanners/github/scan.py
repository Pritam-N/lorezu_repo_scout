from __future__ import annotations

import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from scout.core.config import load_scan_config
from scout.core.engine import run_scan
from scout.core.models import ScanError, ScanResult, ScanStats, ScanTarget, TargetKind
from scout.rules.loader import load_ruleset
from scout.scanners.fs_scanner import read_text_candidate
from scout.scanners.git_scanner import scan_git_repo
from scout.scanners.github.api import GitHubClient, RepoInfo
from scout.scanners.github.clone import CloneOptions, clone_repo
from scout.scanners.github.filters import RepoFilter

EventType = str  # "clone_start"|"clone_done"|"scan_start"|"scan_done"|"repo_error"
OnEvent = Callable[[EventType, str, str], None]  # (event, repo_full_name, message)


@dataclass(frozen=True)
class GitHubScanOptions:
    org: Optional[str] = None
    user: Optional[str] = None

    include_private: bool = True
    include_untracked: bool = True
    include_ignored: Optional[bool] = None

    shallow: bool = True
    blobless: bool = True
    concurrency: int = 4

    tmp_dir: Optional[Path] = None
    keep_clones: bool = False


def _scan_one_repo(
    repo: RepoInfo,
    repo_path: Path,
    *,
    builtin: str,
    rules_files: List[Path],
    ignore_globs: List[str],
    include_untracked: bool,
    include_ignored: Optional[bool],
    clone_ms: int,
    on_event: Optional[OnEvent],
) -> ScanResult:
    # load config + rules per repo (supports .secret-scout in each repo)
    loaded_cfg = load_scan_config(repo_path, cli_overrides={"scan": {}})
    loaded_rules = load_ruleset(repo_path, builtin=builtin, extra_rule_files=rules_files)

    cfg = loaded_cfg.config
    ruleset = loaded_rules.ruleset

    git_root, candidates = scan_git_repo(
        start_dir=repo_path,
        config=cfg,
        include_untracked=include_untracked,
        include_ignored=include_ignored,
        ignore_globs=ignore_globs,
    )

    target = ScanTarget(
        name=repo.full_name,
        kind=TargetKind.GITHUB,
        root_path=str(git_root),
        meta={
            "scanner": "git",
            "html_url": repo.html_url,
            "private": repo.private,
            "archived": repo.archived,
            "fork": repo.fork,
            "clone_ms": clone_ms,
        },
    )

    t0 = time.perf_counter()
    res = run_scan(
        target=target,
        candidates=candidates,
        ruleset=ruleset,
        config=cfg,
        read_text=lambda c: read_text_candidate(c, cfg),
        baseline=None,
        structured_parsers=None,
        dedupe=True,
    )
    scan_ms = int((time.perf_counter() - t0) * 1000)
    # attach scan timing
    if res.targets and res.targets[0].meta is not None:
        res.targets[0].meta["scan_ms"] = scan_ms

    if on_event:
        on_event("scan_done", repo.full_name, f"{len(res.findings)} findings ({scan_ms} ms)")
    return res


def scan_github(
    *,
    client: GitHubClient,
    repo_filter: RepoFilter,
    opts: GitHubScanOptions,
    builtin: str = "default",
    rules_files: Optional[List[Path]] = None,
    ignore_globs: Optional[List[str]] = None,
    on_event: Optional[OnEvent] = None,
) -> Tuple[List[ScanResult], Path]:
    """
    Returns: (results, workspace_dir)

    Events emitted (if on_event provided):
      - clone_start, clone_done, scan_start, scan_done, repo_error
    """
    rules_files = rules_files or []
    ignore_globs = ignore_globs or []

    if not opts.org and not opts.user:
        raise ValueError("Either org or user must be provided.")

    if opts.org:
        repos = client.list_org_repos(opts.org, include_private=opts.include_private)
    else:
        repos = client.list_user_repos(opts.user or "", include_private=opts.include_private)

    repos = repo_filter.apply(repos)

    # workspace
    if opts.tmp_dir:
        workspace = opts.tmp_dir.expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        temp_ctx = None
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="secret-scout-gh-")
        workspace = Path(temp_ctx.name).resolve()

    clones_root = workspace / "clones"
    clones_root.mkdir(parents=True, exist_ok=True)

    clone_opts = CloneOptions(shallow=opts.shallow, depth=1, blobless=opts.blobless)

    results: List[ScanResult] = []

    concurrency = max(1, int(opts.concurrency))
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {}
        for r in repos:
            fut = ex.submit(
                _clone_and_scan,
                r,
                clones_root,
                token=client.token,
                clone_opts=clone_opts,
                builtin=builtin,
                rules_files=rules_files,
                ignore_globs=ignore_globs,
                include_untracked=opts.include_untracked,
                include_ignored=opts.include_ignored,
                on_event=on_event,
            )
            futs[fut] = r.full_name

        for fut in as_completed(futs):
            name = futs.get(fut, "unknown")
            try:
                res = fut.result()
                results.append(res)
            except Exception as e:
                if on_event:
                    on_event("repo_error", name, str(e))

                err_target = ScanTarget(name=name, kind=TargetKind.GITHUB, root_path="", meta={"scanner": "github"})
                sr = ScanResult(targets=[err_target], stats=ScanStats())
                sr.errors.append(ScanError(target=name, message="GitHub repo scan failed", detail=str(e)))
                results.append(sr)

    # cleanup workspace if requested
    if temp_ctx and not opts.keep_clones:
        # TemporaryDirectory cleans up when GC'd / context ends; caller can ignore workspace path.
        pass

    return results, workspace


def _clone_and_scan(
    repo: RepoInfo,
    clones_root: Path,
    *,
    token: Optional[str],
    clone_opts: CloneOptions,
    builtin: str,
    rules_files: List[Path],
    ignore_globs: List[str],
    include_untracked: bool,
    include_ignored: Optional[bool],
    on_event: Optional[OnEvent],
) -> ScanResult:
    if on_event:
        on_event("clone_start", repo.full_name, "")

    t0 = time.perf_counter()
    repo_path = clone_repo(repo, clones_root, token=token, opts=clone_opts)
    clone_ms = int((time.perf_counter() - t0) * 1000)

    if on_event:
        on_event("clone_done", repo.full_name, f"{clone_ms} ms")

    if on_event:
        on_event("scan_start", repo.full_name, "")

    return _scan_one_repo(
        repo,
        repo_path,
        builtin=builtin,
        rules_files=rules_files,
        ignore_globs=ignore_globs,
        include_untracked=include_untracked,
        include_ignored=include_ignored,
        clone_ms=clone_ms,
        on_event=on_event,
    )