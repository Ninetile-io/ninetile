import json

import httpx
import pytest

from ninetile import (
    AsyncNinetileClient,
    Client,
    InsufficientCredits,
    RateLimited,
    SolveFailed,
)

API_KEY = "nt_live_" + "k" * 32


class MockTransport:
    """Returns queued httpx.Responses in order; records every request. No network."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def handler(self, request):
        self.calls.append(request)
        assert self.responses, f"unexpected request: {request.method} {request.url}"
        return self.responses.pop(0)

    def sync_client(self, **kwargs):
        session = httpx.Client(transport=httpx.MockTransport(self.handler))
        return Client(api_key=API_KEY, session=session, **kwargs)

    def async_client(self, **kwargs):
        session = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return AsyncNinetileClient(api_key=API_KEY, session=session, **kwargs)


def solved_payload(solve_id="solve_1", status="solved", **extra):
    body = {
        "id": solve_id,
        "object": "solve",
        "type": "hcaptcha",
        "status": status,
        "token": "P1_" + "a" * 500 if status == "solved" else None,
        "user_agent": "Mozilla/5.0 fake" if status == "solved" else None,
        "error": None,
        "charged_usd": 0.00075 if status == "solved" else None,
    }
    body.update(extra)
    return body


def json_response(status, payload, headers=None):
    return httpx.Response(status, json=payload, headers=headers or {})


def test_solve_success():
    mock = MockTransport([json_response(200, solved_payload())])
    client = mock.sync_client()
    solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert solve.status == "solved"
    assert solve.token.startswith("P1_")
    assert solve.user_agent == "Mozilla/5.0 fake"
    assert solve.raw["charged_usd"] == 0.00075
    request = mock.calls[0]
    assert request.method == "POST" and str(request.url).endswith("/solves")
    assert json.loads(request.content)["sitekey"] == "00000000-0000-0000-0000-000000000000"


def test_solve_202_then_poll_to_200():
    mock = MockTransport([
        json_response(202, solved_payload(status="pending"), {"X-Request-Id": "req-poll"}),
        json_response(202, solved_payload(status="solving")),
        json_response(200, solved_payload(status="solved")),
    ])
    client = mock.sync_client()
    solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login",
                         poll_interval=0.01, timeout=5)
    assert solve.status == "solved"
    methods = [c.method for c in mock.calls]
    assert methods == ["POST", "GET", "GET"]
    assert str(mock.calls[1].url).endswith("/solves/solve_1")


def test_insufficient_credits():
    mock = MockTransport([json_response(402, {"error": {
        "code": "insufficient_credits",
        "message": "The balance does not cover this call.",
        "param": None,
        "request_id": "req-402",
    }}, {"X-Request-Id": "req-402"})])
    client = mock.sync_client()
    with pytest.raises(InsufficientCredits) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.code == "insufficient_credits"
    assert exc.value.status == 402
    assert exc.value.request_id == "req-402"
    assert len(mock.calls) == 1  # never retried


def test_rate_limited_retry_after():
    mock = MockTransport([json_response(429, {"error": {
        "code": "rate_limited",
        "message": "Too many requests.",
        "param": None,
        "request_id": "req-429",
    }}, {"Retry-After": "17", "X-Request-Id": "req-429"})])
    client = mock.sync_client()
    with pytest.raises(RateLimited) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.retry_after == 17
    assert exc.value.status == 429
    assert len(mock.calls) == 1  # a create retry is a new solve: never silently


def test_failed_solve_is_free_and_retryable():
    mock = MockTransport([json_response(200, solved_payload(
        status="failed",
        error={"code": "challenge_not_loaded", "message": "hCaptcha did not serve a challenge.",
               "reason": "sitekey_rate_limited", "retryable": True, "docs_url": None},
    ), {"X-Request-Id": "req-fail"})])
    client = mock.sync_client()
    with pytest.raises(SolveFailed) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.retryable is True
    assert exc.value.reason == "sitekey_rate_limited"
    assert exc.value.code == "challenge_not_loaded"
    assert exc.value.request_id == "req-fail"


async def test_async_solve_success():
    mock = MockTransport([json_response(200, solved_payload())])
    client = mock.async_client()
    solve = await client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert solve.status == "solved"
    assert solve.token.startswith("P1_")
    assert solve.user_agent == "Mozilla/5.0 fake"
    request = mock.calls[0]
    assert request.method == "POST" and str(request.url).endswith("/solves")
    assert json.loads(request.content)["sitekey"] == "00000000-0000-0000-0000-000000000000"


async def test_async_rate_limited_retry_after():
    mock = MockTransport([json_response(429, {"error": {
        "code": "rate_limited",
        "message": "Too many requests.",
        "param": None,
        "request_id": "req-429-async",
    }}, {"Retry-After": "17", "X-Request-Id": "req-429-async"})])
    client = mock.async_client()
    with pytest.raises(RateLimited) as exc:
        await client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.retry_after == 17
    assert exc.value.status == 429
    assert exc.value.request_id == "req-429-async"
    assert len(mock.calls) == 1  # a create retry is a new solve: never silently
