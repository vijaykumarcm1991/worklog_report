"""Tests for the Cloud and On-prem Jira client abstractions (mocked HTTP)."""
import datetime as dt
from types import SimpleNamespace

import httpx
import pytest

from app.jira import (
    JiraAuthError,
    JiraCloudClient,
    JiraOnPremClient,
    make_client,
)
from app.models import Instance


def _make_instance(instance_type="cloud", base_url="https://acme.atlassian.net"):
    return Instance(
        name="Test",
        instance_type=instance_type,
        base_url=base_url,
        username="dev@acme.com",
        token_enc="enc",
    )


class FakeResponse:
    def __init__(self, status_code=200, json=None):
        self.status_code = status_code
        self._json = json
        self.url = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("GET", self.url), response=self)

    def json(self):
        return self._json


class FakeClient:
    """Pretend httpx.Client; returns canned JSON based on the request path."""

    def __init__(self, responses):
        self.responses = responses  # list of FakeResponse, consumed in order
        self.timeout = None
        self.last_request = None  # (method, url, params, json)

    def __enter__(self):
        # Return SELF so the same stub queue is shared across multiple
        # `with httpx.Client(...)` blocks (each request opens its own client).
        return self

    def __exit__(self, *a):
        return False

    def request(self, method, url, headers=None, params=None, json=None):
        self.last_request = (method, url, params, json)
        resp = self.responses.pop(0)
        resp.url = url
        if isinstance(resp, Exception):
            raise resp
        return resp

    def get(self, url, headers=None, params=None):
        return self.request("GET", url, headers=headers, params=params)


def _patch(monkeypatch, *responses) -> FakeClient:
    fake = FakeClient(list(responses))
    monkeypatch.setattr("app.jira.httpx.Client", lambda *a, **k: fake)
    return fake


def test_cloud_uses_api3_and_accountid(monkeypatch, db):
    myself = FakeResponse(
        200,
        {"displayName": "Dev One", "emailAddress": "dev@acme.com"},
    )
    search = FakeResponse(
        200,
        [
            {
                "accountId": "account-id-1",
                "displayName": "Dev One",
                "emailAddress": "dev@acme.com",
                "avatarUrls": {"48x48": "https://a/1.png"},
            }
        ],
    )
    issues = FakeResponse(
        200,
        {
            "issues": [
                {
                    "key": "ACME-1",
                    "fields": {
                        "worklog": {
                            "worklogs": [
                                {
                                    "id": "1001",
                                    "author": {"accountId": "account-id-1"},
                                    "started": "2024-01-15T10:00:00.000+0000",
                                    "timeSpentSeconds": 3600,
                                    "comment": {"type": "doc", "version": 1, "content": [{"type": "text", "text": "did stuff"}]},
                                }
                            ]
                        }
                    },
                }
            ]
        },
    )
    fake = _patch(monkeypatch, myself, search, issues)

    client = make_client(_make_instance("cloud"), "token")
    ok, msg = client.test_connection()
    assert ok is True

    users = client.search_users("dev")
    assert users[0]["user_key"] == "account-id-1"

    wl = client.fetch_worklogs("account-id-1", dt.datetime(2024, 1, 1))
    assert len(wl) == 1
    assert wl[0]["worklog_id"] == "1001"
    assert wl[0]["issue_key"] == "ACME-1"
    assert wl[0]["seconds"] == 3600
    assert wl[0]["comment"] == "did stuff"  # ADF comment flattened to text

    # Cloud must use the CURRENT POST /rest/api/3/search/jql endpoint (GET
    # /search returns 410 Gone), with a JSON body containing the JQL.
    method, url, params, payload = fake.last_request
    assert method == "POST"
    assert url.endswith("/rest/api/3/search/jql")
    assert params is None
    assert "worklogAuthor" in payload["jql"]


def test_cloud_fetches_worklogs_for_customer_account(monkeypatch):
    # On this JSM site, 712020:... customer accounts ARE valid worklog authors
    # and DO return worklogs — they must go through the normal POST /search/jql
    # path, not be blocked.
    myself = FakeResponse(200, {"displayName": "Dev One"})
    issues = FakeResponse(
        200,
        {
            "issues": [
                {
                    "key": "ACME-2",
                    "fields": {
                        "worklog": {
                            "worklogs": [
                                {
                                    "id": "2002",
                                    "author": {"accountId": "712020:5443fc4e-fa4f-420a-ae4a-0b936bf06ed8"},
                                    "started": "2024-01-15T10:00:00.000+0000",
                                    "timeSpentSeconds": 600,
                                    "comment": "support work",
                                }
                            ]
                        }
                    },
                }
            ]
        },
    )
    fake = _patch(monkeypatch, myself, issues)
    client = make_client(_make_instance("cloud"), "token")
    client.test_connection()
    wl = client.fetch_worklogs("712020:5443fc4e-fa4f-420a-ae4a-0b936bf06ed8", dt.datetime(2024, 1, 1))
    assert len(wl) == 1
    assert wl[0]["seconds"] == 600
    # Must have hit the current POST /search/jql endpoint
    method, url, params, payload = fake.last_request
    assert method == "POST"
    assert url.endswith("/rest/api/3/search/jql")


def test_onprem_uses_api2_and_username(monkeypatch):
    myself = FakeResponse(200, {"displayName": "Prem User", "name": "puser"})
    search = FakeResponse(
        200,
        [{"name": "puser", "displayName": "Prem User", "emailAddress": "p@corp.local"}],
    )
    issues = FakeResponse(
        200,
        {
            "issues": [
                {
                    "key": "PREMO-9",
                    "fields": {
                        "worklog": {
                            "worklogs": [
                                {
                                    "id": "88",
                                    "author": {"name": "puser"},
                                    "started": "2024-01-15T09:30:00.000+0000",
                                    "timeSpentSeconds": 7200,
                                    "comment": "ops",
                                }
                            ]
                        }
                    },
                }
            ]
        },
    )
    _patch(monkeypatch, myself, search, issues)

    client = make_client(_make_instance("onprem", "http://jira.corp.local"), "pw")
    ok, _ = client.test_connection()
    assert ok is True
    users = client.search_users("puser")
    assert users[0]["user_key"] == "puser"
    wl = client.fetch_worklogs("puser", dt.datetime(2024, 1, 1))
    assert len(wl) == 1
    assert wl[0]["seconds"] == 7200


def test_auth_error_maps_to_jarrauth(monkeypatch):
    _patch(monkeypatch, FakeResponse(401, None))
    client = make_client(_make_instance("cloud"), "bad-token")
    ok, msg = client.test_connection()
    assert ok is False
    assert "Authentication failed" in msg


def test_parse_iso_keeps_ist_wall_clock():
    from app.jira import _parse_iso

    # IST timestamps are kept exactly as reported: no conversion to UTC.
    d1 = _parse_iso("2024-01-15T02:30:00.000+0530")
    d2 = _parse_iso("2024-01-15T02:30:00.000+05:30")
    assert d1 == d2 == dt.datetime(2024, 1, 15, 2, 30)
    assert d1.tzinfo is None
    # Early-morning IST work stays on its own day.
    assert d1.date() == dt.date(2024, 1, 15)
    assert _parse_iso("2024-01-15T10:00:00Z") == dt.datetime(2024, 1, 15, 10, 0)


def test_non_json_response_is_reported_not_raised(monkeypatch):
    class HtmlResponse(FakeResponse):
        def json(self):
            raise ValueError("not json")

    _patch(monkeypatch, HtmlResponse(200, None))
    client = make_client(_make_instance("onprem", "http://jira.corp.local"), "pw")
    ok, msg = client.test_connection()
    assert ok is False
    assert "non-JSON" in msg


def test_comment_text_flattens_adf():
    from app.jira import _comment_text

    # Cloud returns ADF objects for comments; must flatten to a string.
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "did "}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "the work"}]},
        ],
    }
    assert _comment_text(adf) == "did the work"
    # Plain string passes through
    assert _comment_text("plain comment") == "plain comment"
    # None / empty-safe
    assert _comment_text(None) == ""
