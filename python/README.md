<div align="center">

# ninetile

Official Python client for the [Ninetile API](https://ninetile.io/docs) — send a sitekey and URL, get back a token your form can submit, or send a challenge's images and get back where to click.

[![CI](https://img.shields.io/github/actions/workflow/status/Ninetile-io/ninetile/test-python.yml?branch=main)](https://github.com/Ninetile-io/ninetile/actions/workflows/test-python.yml)
[![PyPI version](https://img.shields.io/pypi/v/ninetile)](https://pypi.org/project/ninetile/)
[![Python versions](https://img.shields.io/pypi/pyversions/ninetile)](https://pypi.org/project/ninetile/)
[![License](https://img.shields.io/github/license/Ninetile-io/ninetile)](https://github.com/Ninetile-io/ninetile/blob/main/LICENSE)

</div>

## Install

```bash
pip install ninetile
```

`0.1.0` is the version in this repo; until it reaches PyPI, install from the repository instead: `pip install ./python`. Requires Python 3.9+.

Get a key at [ninetile.io/signup](https://ninetile.io/signup); the key (`nt_live_…`) is shown once. Every request sends `Authorization: Bearer nt_live_…`.

## Browser identity

Do not send a `user_agent`. The API refuses it with `422 validation_error` (`param: "user_agent"`)
because a token is minted inside one coherent browser identity — User-Agent, Sec-CH-UA client hints
and platform must agree — and an arbitrary string breaks that agreement. Submit the token with the
`solve.user_agent` the API returns; an empty string is treated as omitted. The client passes unknown
keyword fields through to the request body, so `client.solve(..., user_agent="...")` reaches the API
and is refused.

## Quick start

Sync:

```python
from ninetile import NinetileClient

client = NinetileClient()  # reads NT_API_KEY
solve = client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login", wait=30)
print(solve.status, solve.token)
```

Async:

```python
import asyncio
from ninetile import AsyncNinetileClient

async def main():
    async with AsyncNinetileClient() as client:  # reads NT_API_KEY
        solve = await client.solve("00000000-0000-0000-0000-000000000000", "https://target.example/login", wait=30)
        print(solve.status, solve.token)

asyncio.run(main())
```

Submit `solve.token` with the `User-Agent` from `solve.user_agent` — tokens are single-use and expire within minutes. Omit `wait` to have the client poll instead of holding the connection open server-side; `solve()` blocks (or awaits) until the solve is final and raises `SolveFailed` if it ends without a token. `client.recognize(task=..., image_data=[...])` answers a challenge's images instead of minting a token; `AsyncNinetileClient` has the same methods, awaited.

## Errors

Every non-2xx response has the same shape: `{"error": {"code", "message", "param", "request_id"}}`. The SDK raises typed exceptions — `AuthenticationError` (401), `InsufficientCredits` (402), `RateLimited` (429, with `retry_after`; honour `Retry-After`), else `NinetileError` — each carrying `code`, `status` and `request_id` (quote `request_id`, or the `X-Request-Id` response header, when you contact support). A solve can also end without a token: `SolveFailed`, with `retryable` and `reason` — never an HTTP error, and never charged. Failed work is never charged; retry only when the solve's `error.retryable` is true, and only by calling `solve()` again — the create call is never retried silently.

## Links

- Docs: https://ninetile.io/docs
- Dashboard: https://ninetile.io/dashboard
