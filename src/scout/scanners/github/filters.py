from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from scout.core.matcher import any_glob_match, normalize_rel_path
from scout.scanners.github.api import RepoInfo


@dataclass(frozen=True)
class RepoFilter:
    include: Sequence[str] = ()
    exclude: Sequence[str] = ()
    repos: Sequence[str] = ()  # explicit allow list of full_names (org/repo)

    include_archived: bool = False
    include_forks: bool = False
    include_disabled: bool = False

    max_repos: Optional[int] = None

    def apply(self, repos: Iterable[RepoInfo]) -> List[RepoInfo]:
        allow: Set[str] = {r.lower() for r in self.repos} if self.repos else set()

        out: List[RepoInfo] = []
        for r in repos:
            name = r.full_name or f"{r.owner_login}/{r.name}"
            key = name.lower()

            if allow and key not in allow:
                continue

            if not self.include_archived and r.archived:
                continue
            if not self.include_forks and r.fork:
                continue
            if not self.include_disabled and r.disabled:
                continue

            if self.exclude and any_glob_match(normalize_rel_path(name), self.exclude):
                continue

            if self.include and not any_glob_match(normalize_rel_path(name), self.include):
                continue

            out.append(r)

        # stable order
        out.sort(key=lambda x: (x.full_name or "", x.id))
        if self.max_repos is not None:
            out = out[: int(self.max_repos)]
        return out