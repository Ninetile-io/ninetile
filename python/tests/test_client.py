import pytest

from ninetile import (
    Client,
    InsufficientCredits,
    RateLimited,
    SolveFailed,
)


class FakeResponse:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    """Returns queued FakeResponses in order; records every call. No network."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


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


def make_client(responses, **kwargs):
    return Client(api_key="nt_live_" + "k" * 32, session=FakeSession(responses), **kwargs)


def test_solve_success():
    client = make_client([FakeResponse(200, solved_payload())])
    solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert solve.status == "solved"
    assert solve.token.startswith("P1_")
    assert solve.user_agent == "Mozilla/5.0 fake"
    assert solve.raw["charged_usd"] == 0.00075
    (method, url, kwargs) = client.session.calls[0]
    assert method == "POST" and url.endswith("/solves")
    assert kwargs["json"]["sitekey"] == "00000000-0000-0000-0000-000000000000"


def test_solve_202_then_poll_to_200():
    client = make_client([
        FakeResponse(202, solved_payload(status="pending"), {"X-Request-Id": "req-poll"}),
        FakeResponse(202, solved_payload(status="solving")),
        FakeResponse(200, solved_payload(status="solved")),
    ])
    solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login",
                         poll_interval=0.01, timeout=5)
    assert solve.status == "solved"
    methods = [c[0] for c in client.session.calls]
    assert methods == ["POST", "GET", "GET"]
    assert client.session.calls[1][1].endswith("/solves/solve_1")


def test_insufficient_credits():
    client = make_client([FakeResponse(402, {"error": {
        "code": "insufficient_credits",
        "message": "The balance does not cover this call.",
        "param": None,
        "request_id": "req-402",
    }}, {"X-Request-Id": "req-402"})])
    with pytest.raises(InsufficientCredits) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.code == "insufficient_credits"
    assert exc.value.status == 402
    assert exc.value.request_id == "req-402"
    assert len(client.session.calls) == 1  # never retried


def test_rate_limited_retry_after():
    client = make_client([FakeResponse(429, {"error": {
        "code": "rate_limited",
        "message": "Too many requests.",
        "param": None,
        "request_id": "req-429",
    }}, {"Retry-After": "17", "X-Request-Id": "req-429"})])
    with pytest.raises(RateLimited) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.retry_after == 17
    assert exc.value.status == 429
    assert len(client.session.calls) == 1  # a create retry is a new solve: never silently


def test_failed_solve_is_free_and_retryable():
    client = make_client([FakeResponse(200, solved_payload(
        status="failed",
        error={"code": "challenge_not_loaded", "message": "hCaptcha did not serve a challenge.",
               "reason": "sitekey_rate_limited", "retryable": True, "docs_url": None},
    ), {"X-Request-Id": "req-fail"})])
    with pytest.raises(SolveFailed) as exc:
        client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login")
    assert exc.value.retryable is True
    assert exc.value.reason == "sitekey_rate_limited"
    assert exc.value.code == "challenge_not_loaded"
    assert exc.value.request_id == "req-fail"
