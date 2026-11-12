# Ninetile

Ninetile is an hCaptcha API: send a sitekey and URL, get back a token your form can submit — or send a challenge's images, get back where to click.

This repository is the public home for the Ninetile API and its client libraries. Today it documents the API itself; `python/` and `javascript/` SDKs are being prepared in this repo and are **not published yet** (see [Roadmap](#roadmap)).

Documentation: [ninetile.io/docs](https://ninetile.io/docs) · Dashboard: [ninetile.io/dashboard](https://ninetile.io/dashboard)

## Token API vs Recognition API

| | Token API | Recognition API |
|---|---|---|
| What it does | Solves the challenge for you; returns a `P1_` token | Answers the challenge; returns tile selections / click points / drag boxes |
| Endpoint | `POST https://api.ninetile.io/v1/solves` | `POST https://api.ninetile.io/v1/recognize` |
| For | Integrations that want a ready-to-submit token | Integrations that run their own browser and only need the answer |
| Price | **$0.75 per 1,000** successful tokens | **$0.30 per 1,000** successful answers |
| Failed work | Free | Free |

Prices are prepaid USD, charged only for work that succeeds. Failed, cancelled and expired solves and unanswerable puzzles cost nothing.

## Getting a key

1. Create an account at [ninetile.io/signup](https://ninetile.io/signup).
2. Add prepaid balance (top-ups are handled by the operator; see the dashboard billing page).
3. Create an API key in the [dashboard](https://ninetile.io/dashboard). The key (`nt_live_…`) is shown once; only its hash is stored.

Every request sends the key as `Authorization: Bearer nt_live_…` (`x-api-key: nt_live_…` also works).

## Quickstart: Token API

```bash
curl "https://api.ninetile.io/v1/solves?wait=30" \
  -H "Authorization: Bearer $NT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"hcaptcha","sitekey":"00000000-0000-0000-0000-000000000000","url":"https://target.example/login"}'
```

`?wait=30` holds the connection for up to 90 seconds until the solve is final. Without it you get `202` immediately and poll `GET /v1/solves/{id}`. A solved response carries `token` and the `user_agent` the solve ran as — submit the token with exactly that User-Agent. Tokens are single-use and expire within minutes.

## Quickstart: Recognition API

```bash
curl https://api.ninetile.io/v1/recognize \
  -H "Authorization: Bearer $NT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"hcaptcha","task":"Select all bicycles","image_data":["<BASE64_TILE_1>","<BASE64_TILE_2>"]}'
```

`image_data` takes 1–27 base64 tiles in reading order (or `image_urls` with hCaptcha image URLs). The response `data` is one boolean per tile, in order:

```json
{ "id": "rec_…", "data": [true, false], "charged_usd": 0.0003 }
```

Use `type: "hcaptcha_area_select"` with exactly one image for point challenges. The full challenge form (`{"data": {…}}`) covers drag-and-drop and enterprise challenges — see the [docs](https://ninetile.io/docs/recognition-api).

## Python

```python
import os, requests

r = requests.post(
    "https://api.ninetile.io/v1/solves",
    params={"wait": 30},
    headers={"Authorization": f"Bearer {os.environ['NT_API_KEY']}"},
    json={"type": "hcaptcha",
          "sitekey": "00000000-0000-0000-0000-000000000000",
          "url": "https://target.example/login"},
    timeout=95,
)
r.raise_for_status()
solve = r.json()
print(solve["status"], solve.get("token"))
```

## Node.js

```js
const axios = require("axios");

const { data: solve } = await axios.post(
  "https://api.ninetile.io/v1/solves?wait=30",
  { type: "hcaptcha",
    sitekey: "00000000-0000-0000-0000-000000000000",
    url: "https://target.example/login" },
  { headers: { Authorization: `Bearer ${process.env.NT_API_KEY}` }, timeout: 95000 },
);
console.log(solve.status, solve.token);
```

## Errors

Every non-2xx response has the same shape:

```json
{ "error": { "code": "insufficient_credits", "message": "…", "param": null, "request_id": "9f1c2d3e-…" } }
```

A request that was accepted can still end without a token: the solve comes back with `status: failed` and an `error` object (`code`, `message`, `reason`, `retryable`) — never an HTTP error, and never charged. Retry only failures marked `retryable`, and honour `Retry-After`. The full code table is in the [errors guide](https://ninetile.io/docs/errors-and-limits); `401 unauthorized` means a missing or wrong key.

Responses carry `X-Request-Id` — quote it when you contact support.

## Coming from another solver

The same key works on the compatibility routes: `…/compat/2captcha` (`in.php`/`res.php`), `…/compat/capsolver` (also `/compat/anticaptcha`, `/compat/capmonster`), and `…/compat/nopecha`. Only hCaptcha task types are served; other types are refused in the dialect's own error format.

## Roadmap

- `python/` — official `ninetile` package for PyPI (requests-based, like the snippets above). In this repo, not published yet.
- `javascript/` — official `ninetile` package for npm. In this repo, not published yet.
- `extension/` — Chrome extension. Not available; the site announces it when it ships.

When the packages publish, this section will change and install instructions will appear here. Until then, the curl/requests/axios examples above are the supported integration path.

## Status and support

`GET https://api.ninetile.io/v1/status` is a public liveness check. Docs: [ninetile.io/docs](https://ninetile.io/docs) · API reference: [ninetile.io/docs/api-reference/create-solve](https://ninetile.io/docs/api-reference/create-solve) · Dashboard: [ninetile.io/dashboard](https://ninetile.io/dashboard)
