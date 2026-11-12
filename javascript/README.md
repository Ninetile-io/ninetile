<div align="center">

# ninetile

Official JavaScript/TypeScript client for the [Ninetile API](https://ninetile.io/docs) — send a sitekey and URL, get back a token your form can submit.

[![CI](https://img.shields.io/github/actions/workflow/status/Ninetile-io/ninetile/test-js.yml?branch=main)](https://github.com/Ninetile-io/ninetile/actions/workflows/test-js.yml)
[![npm version](https://img.shields.io/npm/v/ninetile)](https://www.npmjs.com/package/ninetile)
[![Node](https://img.shields.io/node/v/ninetile)](https://www.npmjs.com/package/ninetile)
[![License](https://img.shields.io/github/license/Ninetile-io/ninetile)](https://github.com/Ninetile-io/ninetile/blob/main/LICENSE)

</div>

## Install

```bash
npm install ninetile
```

`0.1.0` is the version in this repo; until it reaches npm, install from the repository instead: `npm install ./javascript`.

## Quick start

```js
import { NinetileClient } from 'ninetile';

const client = new NinetileClient(); // reads NT_API_KEY

const solve = await client.solve(
  '00000000-0000-0000-0000-000000000000',
  'https://target.example/login',
  { wait: 30 }, // omit to poll instead of holding the connection
);

console.log(solve.status, solve.token);
```

Submit `solve.token` with the `User-Agent` from `solve.userAgent` — tokens are single-use and expire within minutes. Node 18+, zero runtime dependencies (global `fetch`), ESM and CJS. `client.recognize({ task, imageData, ... })` answers a challenge's images instead of minting a token.

`user_agent` is not a parameter: the API refuses a supplied `user_agent` with `422 validation_error` (`param: "user_agent"`; an empty string is treated as omitted). The token is minted inside one coherent browser identity — User-Agent, Sec-CH-UA client hints and platform must agree — so submit it with the `User-Agent` from `solve.userAgent`, the authoritative one. Unknown option fields are merged into the request body verbatim, so a `user_agent` key passed in the options object reaches the API as-is and is refused — leave it out.

## Errors

Every non-2xx response has the same shape: `{"error": {code, message, param, request_id}}`. The SDK throws typed exceptions — `AuthenticationError` (401), `InsufficientCredits` (402), `RateLimited` (429, with `retryAfter`; honour `Retry-After`), else `NinetileError` — each carrying `code`, `status` and `requestId` (quote `requestId` or the `X-Request-Id` header when you contact support). A solve can also end without a token: `SolveFailed`, with `retryable` and `reason` — never an HTTP error, and never charged.

## Links

- Docs: https://ninetile.io/docs
- Dashboard: https://ninetile.io/dashboard
