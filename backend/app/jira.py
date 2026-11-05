"""Jira client abstractions for Cloud and On-prem (Server/DC) instances.

Both implement the same fetch interface so the rest of the app is agnostic to
instance type. Key differences handled here:

- API base path:        Cloud /rest/api/3   vs  On-prem /rest/api/2
- User identity field:  Cloud accountId   vs   On-prem username/key/name
- Auth:                 both use HTTP Basic (email+token for cloud,
                        username+token/password for on-prem)
"""
from __future__ import annotations

import base64
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

from .models import Instance
from .timeutil import now_ist


class JiraAuthError(Exception):
    """Failure contacting the instance: bad credentials, wrong URL, or a
    response that isn't the Jira REST API (e.g. an SSO login page)."""


class JiraClient(ABC):
    instance_type: str = ""

    def __init__(self, instance: Instance, token: str, timeout: float = 20.0):
        self.instance = instance
        self.token = token
        self.timeout = timeout
        # Trim trailing slash so URL joins are clean
        self.base_url = instance.base_url.rstrip("/")

    # -- auth ----------------------------------------------------------------
    def _auth_headers(self) -> dict[str, str]:
        raw = f"{self.instance.username}:{self.token}"
        b64 = base64.b64encode(raw.encode()).decode()
        return {"Authorization": f"Basic {b64}"}

    # -- http helpers --------------------------------------------------------
    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, verify=True) as client:
            resp = client.request(method, url, headers=self._auth_headers(), params=params, json=json)
        if resp.status_code in (401, 403):
            raise JiraAuthError(
                f"Authentication failed for {self.instance.name} (HTTP {resp.status_code}). "
                "Check the email/username and API token."
            )
        if resp.status_code == 404:
            raise JiraAuthError(
                f"Endpoint not found for {self.instance.name} (HTTP 404). "
                "Check the base URL / site address."
            )
        if resp.status_code == 410:
            raise JiraAuthError(
                f"Endpoint retired for {self.instance.name} (HTTP 410 Gone). "
                "The Jira search API has changed; update the backend."
            )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise JiraAuthError(
                f"{self.instance.name} returned a non-JSON response (HTTP {resp.status_code}). "
                "Check the base URL; an SSO/login page or proxy may be answering instead of Jira."
            ) from exc

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", url, params=params)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", url, json=payload)

    def _api(self, path: str) -> str:
        raise NotImplementedError

    def _all_issue_worklogs(self, issue: dict) -> list[dict]:
        """Return every worklog of an issue.

        Search results embed at most ~20 worklogs per issue; when the issue has
        more, page through /issue/{key}/worklog to get the rest.
        """
        wl = (issue.get("fields") or {}).get("worklog") or {}
        entries = list(wl.get("worklogs", []))
        total = wl.get("total", len(entries))
        key = issue.get("key", "")
        if total <= len(entries) or not key:
            return entries
        entries = []
        start = 0
        while True:
            page = self._get(self._api(f"/issue/{key}/worklog"), params={"startAt": start, "maxResults": 1000})
            batch = page.get("worklogs", [])
            entries.extend(batch)
            start += len(batch)
            if not batch or start >= page.get("total", start):
                break
        return entries

    # -- public API ----------------------------------------------------------
    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Return (ok, message). Should not raise on cred errors."""

    @abstractmethod
    def search_users(self, query: str, max_results: int = 20) -> list[dict]:
        """Search users; returns list of {user_key, display_name, email, avatar_url}."""

    @abstractmethod
    def fetch_worklogs(self, user_key: str, since: datetime) -> list[dict]:
        """Return list of {worklog_id, worklog_date(datetime), seconds, comment, issue_key}."""


class JiraCloudClient(JiraClient):
    instance_type = "cloud"

    # -- helpers -------------------------------------------------------------
    def _api(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3{path}"

    # -- connection ----------------------------------------------------------
    def test_connection(self) -> tuple[bool, str]:
        try:
            data = self._get(self._api("/myself"))
        except JiraAuthError as exc:
            return False, str(exc)
        except httpx.HTTPError as exc:
            return False, f"Could not reach instance: {exc}"
        name = (data.get("displayName") or "").strip()
        return True, f"Connected to Jira Cloud as {name or self.instance.username}"

    # -- users ---------------------------------------------------------------
    def search_users(self, query: str, max_results: int = 20) -> list[dict]:
        # Cloud user/search requires 'query'. 'active' filters to active users.
        data = self._get(
            self._api("/user/search"),
            params={"query": query, "maxResults": max_results, "active": "true"},
        )
        out: list[dict] = []
        for u in data:
            avatar = ""
            av = u.get("avatarUrls") or {}
            for key in ("48x48", "32x32", "24x24", "16x16"):
                if av.get(key):
                    avatar = av[key]
                    break
            out.append(
                {
                    "user_key": u.get("accountId", ""),
                    "display_name": u.get("displayName", "") or u.get("name", ""),
                    "email": u.get("emailAddress", ""),
                    "avatar_url": avatar,
                }
            )
        return out

    # -- worklogs ------------------------------------------------------------
    def fetch_worklogs(self, user_key: str, since: datetime) -> list[dict]:
        since_str = since.strftime("%Y-%m-%d")
        until_str = now_ist().strftime("%Y-%m-%d")
        jql = (
            f'worklogAuthor = "{_jql_quote(user_key)}" '
            f'AND worklogDate >= "{since_str}" AND worklogDate <= "{until_str}"'
        )
        # NOTE: Jira Cloud retired the GET /rest/api/3/search endpoint (410 Gone).
        # The current endpoint is POST /rest/api/3/search/jql with a JSON body,
        # paginated with nextPageToken.
        out: list[dict] = []
        page_token: str | None = None
        while True:
            payload: dict[str, Any] = {
                "jql": jql,
                "maxResults": 100,
                "fields": ["summary", "worklog"],
            }
            if page_token:
                payload["nextPageToken"] = page_token
            data = self._post_json(self._api("/search/jql"), payload)
            for issue in data.get("issues", []):
                issue_key = issue.get("key", "")
                for entry in self._all_issue_worklogs(issue):
                    if (entry.get("author") or {}).get("accountId") != user_key:
                        continue
                    started = entry.get("started")
                    if not started:
                        continue
                    dt = _parse_iso(started)
                    if dt >= since:
                        out.append(
                            {
                                "worklog_id": str(entry.get("id", "")),
                                "worklog_date": dt,
                                "seconds": int(entry.get("timeSpentSeconds", 0)),
                                "comment": _comment_text(entry.get("comment")),
                                "issue_key": issue_key,
                            }
                        )
            page_token = data.get("nextPageToken")
            if not page_token or data.get("isLast", False):
                break
        return out


class JiraOnPremClient(JiraClient):
    instance_type = "onprem"

    def _api(self, path: str) -> str:
        return f"{self.base_url}/rest/api/2{path}"

    # -- connection ----------------------------------------------------------
    def test_connection(self) -> tuple[bool, str]:
        try:
            data = self._get(self._api("/myself"))
        except JiraAuthError as exc:
            return False, str(exc)
        except httpx.HTTPError as exc:
            return False, f"Could not reach instance: {exc}"
        name = (data.get("displayName") or "").strip()
        return True, f"Connected to Jira as {name or self.instance.username}"

    # -- users ---------------------------------------------------------------
    def search_users(self, query: str, max_results: int = 20) -> list[dict]:
        # On-prem user/search uses 'username'. Empty query returns all-ish.
        data = self._get(
            self._api("/user/search"),
            params={"username": query, "maxResults": max_results},
        )
        out: list[dict] = []
        for u in data:
            avatar = ""
            av = u.get("avatarUrls") or {}
            for key in ("48x48", "32x32", "24x24", "16x16"):
                if av.get(key):
                    avatar = av[key]
                    break
            out.append(
                {
                    # On-prem users keyed by 'name' (username).
                    "user_key": u.get("name", "") or u.get("key", ""),
                    "display_name": u.get("displayName", "") or u.get("name", ""),
                    "email": u.get("emailAddress", ""),
                    "avatar_url": avatar,
                }
            )
        return out

    # -- worklogs ------------------------------------------------------------
    def fetch_worklogs(self, user_key: str, since: datetime) -> list[dict]:
        since_str = since.strftime("%Y-%m-%d")
        until_str = now_ist().strftime("%Y-%m-%d")
        # On-prem identify the author by 'name' (username). Order by issue key
        # so offset pagination is stable (no issue repeated or skipped).
        jql = (
            f'worklogAuthor = "{_jql_quote(user_key)}" '
            f'AND worklogDate >= "{since_str}" AND worklogDate <= "{until_str}" '
            f"ORDER BY key ASC"
        )
        out: list[dict] = []
        start = 0
        while True:
            data = self._get(
                self._api("/search"),
                params={"jql": jql, "fields": "worklog", "maxResults": 50, "startAt": start},
            )
            batch = data.get("issues", [])
            for issue in batch:
                issue_key = issue.get("key", "")
                for entry in self._all_issue_worklogs(issue):
                    a_ = entry.get("author") or {}
                    author = a_.get("name") or a_.get("key") or a_.get("accountId")
                    if author != user_key:
                        continue
                    started = entry.get("started")
                    if not started:
                        continue
                    dt = _parse_iso(started)
                    if dt >= since:
                        out.append(
                            {
                                "worklog_id": str(entry.get("id", "")),
                                "worklog_date": dt,
                                "seconds": int(entry.get("timeSpentSeconds", 0)),
                                "comment": _comment_text(entry.get("comment")),
                                "issue_key": issue_key,
                            }
                        )
            start += len(batch)
            if not batch or start >= data.get("total", 0):
                break
        return out


def _jql_quote(value: str) -> str:
    """Escape a value for use inside a double-quoted JQL string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _comment_text(comment: Any) -> str:
    """Flatten a Jira comment to plain text.

    Cloud (REST v3) returns worklog comments as an Atlassian Document Format
    (ADF) object like {"type":"doc","version":1,"content":[...]}; on-prem
    (API v2) usually returns a plain string. Handle both.
    """
    if isinstance(comment, str):
        return comment
    if isinstance(comment, dict):
        # Walk ADF content blocks, joining text leaves.
        parts: list[str] = []

        def walk(node: dict) -> None:
            if not isinstance(node, dict):
                return
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            content = node.get("content")
            if isinstance(content, list):
                for child in content:
                    walk(child)

        walk(comment)
        return "".join(parts).strip()
    return ""


def _parse_iso(value: str) -> datetime:
    """Parse a Jira timestamp such as "2024-01-15T10:00:00.000+0530".

    Both instances are IST, so the wall-clock time Jira reports is kept as-is:
    the offset is dropped, never converted.
    """
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1]
    else:
        v = re.sub(r"[+-]\d{2}:?\d{2}$", "", v)
    return datetime.fromisoformat(v).replace(tzinfo=None)


def make_client(instance: Instance, token: str) -> JiraClient:
    if instance.instance_type == "cloud":
        return JiraCloudClient(instance, token)
    return JiraOnPremClient(instance, token)
