# ninetile (Python SDK)

The official Python client for the [Ninetile API](https://ninetile.io/docs) — send a sitekey and URL, get back a token your form can submit, or send a challenge's images and get back where to click.

`python-requests`-based, like the raw snippets in the repo root. Requires Python 3.9+.

```bash
pip install ninetile  # 0.1.0 is the current release
```

Until 0.1.0 reaches PyPI, install from this repository instead: `pip install ./python`.

Get a key at [ninetile.io/signup](https://ninetile.io/signup); the key (`nt_live_…`) is shown once. Every request sends `Authorization: Bearer nt_live_…`.

## Token API

```python
import os
from ninetile import Client

client = Client()  # reads NT_API_KEY
solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login", wait=30)
print(solve.status, solve.token)
# submit solve.token with the User-Agent solve.user_agent — tokens are single-use
```

One solve costs **$0.00075** (charged only when it succeeds; failed work is free).
`client.solve(...)` blocks until the solve is final and raises `SolveFailed` if it ends without a token (carrying `retryable` and `reason`). Failed work is never charged, so retry only when `retryable` is true — and only by calling `solve()` again: a retry is a new solve. Pass `wait=N` (1–90 seconds) to hold the create request open server-side, or use `client.get_solve(solve.id)` for manual polling.

## Recognition API

```python
result = client.recognize(
    type="hcaptcha",
    task="Select all bicycles",
    image_data=["<BASE64_TILE_1>", "<BASE64_TILE_2>"],  # or image_urls=[...]
)
print(result.data)  # one boolean per tile, in reading order
```

Use `type="hcaptcha_area_select"` with exactly one image for point challenges (`result.data` is a `{x, y, w, h}` box, `result.points` lists the points). For drag-and-drop and enterprise challenges, pass the full challenge form: `client.recognize(data={"request_type": "image_drag_drop", ...})`.

One recognition costs **$0.0003**, charged only when answered.

## Errors

Every non-2xx response has the same shape: `{"error": {"code", "message", "param", "request_id"}}`. The SDK raises typed exceptions — `AuthenticationError` (401), `InsufficientCredits` (402), `RateLimited` (429, with `retry_after`; honour `Retry-After`), `NinetileError` for everything else — each carrying `code`, `status` and `request_id` (quote `request_id`, or the `X-Request-Id` response header, when you contact support). A solve that was accepted can still end without a token: `SolveFailed` with `status="failed"` and an `error` object — never an HTTP error, and never charged.

## Status and support

`GET https://api.ninetile.io/v1/status` is a public liveness check. Docs: [ninetile.io/docs](https://ninetile.io/docs) · API reference: [create-solve](https://ninetile.io/docs/api-reference/create-solve) · Dashboard: [ninetile.io/dashboard](https://ninetile.io/dashboard)
