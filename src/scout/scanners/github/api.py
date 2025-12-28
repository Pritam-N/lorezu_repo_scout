from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class RepoInfo:
    id: int
    name: str
    full_name: str
    clone_url: str
    ssh_url: str
    html_url: str
    private: bool
    fork: bool
    archived: bool
    disabled: bool
    default_branch: str
    owner_login: str


class GitHubAPIError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


def _parse_link_header(link: str) -> Dict[str, str]:
    """
    Parse GitHub Link header into rel->url.
    """
    out: Dict[str, str] = {}
    if not link:
        return out
    parts = [p.strip() for p in link.split(",") if p.strip()]
    for p in parts:
        # <url>; rel="next"
        if ";" not in p:
            continue
        url_part, *params = [x.strip() for x in p.split(";")]
        if not (url_part.startswith("<") and url_part.endswith(">")):
            continue
        url = url_part[1:-1]
        rel = None
        for param in params:
            if param.startswith("rel="):
                rel = param.split("=", 1)[1].strip().strip('"')
        if rel:
            out[rel] = url
    return out


class GitHubClient:
    def __init__(
        self,
        token: Optional[str] = None,
        api_base: str = "https://api.github.com",
        user_agent: str = "repo-scout",
        timeout_s: int = 30,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.api_base = api_base.rstrip("/")
        self.user_agent = user_agent
        self.timeout_s = timeout_s

    def _headers(self) -> Dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request_json(self, url: str, *, retry: int = 3) -> Tuple[Any, Dict[str, str], int]:
        """
        Returns: (json_data, headers_lower, status_code)
        """
        last_err: Optional[Exception] = None
        for attempt in range(retry):
            try:
                req = urllib.request.Request(url, headers=self._headers(), method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    status = int(getattr(resp, "status", 200))
                    raw = resp.read()
                    headers = {k.lower(): v for k, v in resp.headers.items()}
                    data = json.loads(raw.decode("utf-8", errors="replace")) if raw else None
                    return data, headers, status
            except urllib.error.HTTPError as e:
                status = int(getattr(e, "code", 0) or 0)
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = ""
                # rate limit / abuse / transient
                if status in (429, 500, 502, 503, 504):
                    time.sleep(0.5 * (attempt + 1))
                    last_err = e
                    continue
                # 403 can be rate limit too; check headers if possible
                if status == 403:
                    last_err = e
                    raise GitHubAPIError("GitHub API forbidden (possible rate limit or insufficient scopes).", status=status, detail=body)
                raise GitHubAPIError("GitHub API request failed.", status=status, detail=body) from e
            except Exception as e:
                last_err = e
                time.sleep(0.25 * (attempt + 1))
                continue
        raise GitHubAPIError("GitHub API request failed after retries.", detail=str(last_err))

    def _paginate(self, first_url: str) -> Iterable[Dict[str, Any]]:
        url = first_url
        while True:
            data, headers, status = self._request_json(url)
            if status >= 400:
                raise GitHubAPIError("GitHub API error.", status=status, detail=str(data))
            if not isinstance(data, list):
                # some endpoints return dict; allow single-page dict->repos list shape
                raise GitHubAPIError("Unexpected GitHub response (expected list).", status=status, detail=str(data)[:500])
            for item in data:
                if isinstance(item, dict):
                    yield item

            link = headers.get("link", "")
            links = _parse_link_header(link)
            nxt = links.get("next")
            if not nxt:
                break
            url = nxt

    def list_org_repos(
        self,
        org: str,
        *,
        include_private: bool = True,
        per_page: int = 100,
    ) -> List[RepoInfo]:
        # org repos endpoint requires token for private visibility
        q = {"per_page": str(per_page), "type": "all"}
        url = f"{self.api_base}/orgs/{urllib.parse.quote(org)}/repos?{urllib.parse.urlencode(q)}"
        repos = [self._to_repoinfo(x) for x in self._paginate(url)]
        if not include_private:
            repos = [r for r in repos if not r.private]
        return repos

    def list_user_repos(
        self,
        user: str,
        *,
        include_private: bool = True,
        per_page: int = 100,
    ) -> List[RepoInfo]:
        """
        If include_private=True and token exists, use /user/repos and filter by owner login == user.
        Otherwise fallback to /users/{user}/repos (public only).
        """
        if include_private and self.token:
            q = {"per_page": str(per_page), "affiliation": "owner,collaborator,organization", "visibility": "all"}
            url = f"{self.api_base}/user/repos?{urllib.parse.urlencode(q)}"
            repos = [self._to_repoinfo(x) for x in self._paginate(url)]
            # keep only repos owned by requested user
            repos = [r for r in repos if r.owner_login.lower() == user.lower()]
            return repos

        q = {"per_page": str(per_page), "type": "all"}
        url = f"{self.api_base}/users/{urllib.parse.quote(user)}/repos?{urllib.parse.urlencode(q)}"
        repos = [self._to_repoinfo(x) for x in self._paginate(url)]
        if not include_private:
            repos = [r for r in repos if not r.private]
        return repos

    def _to_repoinfo(self, d: Dict[str, Any]) -> RepoInfo:
        owner = d.get("owner") or {}
        return RepoInfo(
            id=int(d.get("id") or 0),
            name=str(d.get("name") or ""),
            full_name=str(d.get("full_name") or ""),
            clone_url=str(d.get("clone_url") or ""),
            ssh_url=str(d.get("ssh_url") or ""),
            html_url=str(d.get("html_url") or ""),
            private=bool(d.get("private") or False),
            fork=bool(d.get("fork") or False),
            archived=bool(d.get("archived") or False),
            disabled=bool(d.get("disabled") or False),
            default_branch=str(d.get("default_branch") or "main"),
            owner_login=str(owner.get("login") or ""),
        )