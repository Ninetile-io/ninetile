# ninetile (JavaScript/TypeScript SDK)

The official JavaScript/TypeScript client for the [Ninetile API](https://ninetile.io/docs) — send a sitekey and URL, get back a token your form can submit, or send a challenge's images and get back where to click.

Zero runtime dependencies; uses the global `fetch` (Node 18+). Ships ESM and CJS with type declarations.

```bash
npm install ninetile  # 0.1.0 is the current release
```

Until 0.1.0 reaches npm, install from this repository instead: `npm install ./javascript`.

Get a key at [ninetile.io/signup](https://ninetile.io/signup); the key (`nt_live_…`) is shown once. Every request sends `Authorization: Bearer nt_live_…`.

## Token API

```js
import { NinetileClient } from 'ninetile';

const client = new NinetileClient(); // reads NT_API_KEY
const solve = await client.solve(
  '00000000-0000-0000-0000-000000000000',
  'https://target.example/login',
  { wait: 30 }, // or omit and let it poll
);
console.log(solve.status, solve.token);
// submit solve.token with the User-Agent solve.userAgent — tokens are single-use
```

One solve costs **$0.00075** (charged only when it succeeds; failed work is free).
`client.solve(...)` resolves once the solve is final and throws `SolveFailed` if it ends without a token (carrying `retryable` and `reason`). Failed work is never charged, so retry only when `retryable` is true — and only by calling `solve()` again: a retry is a new solve. Pass `wait` (1–90 seconds) to hold the create request open server-side, or use `client.getSolve(solve.id)` for manual polling. Reading the key from elsewhere? Pass `new NinetileClient({ apiKey, baseUrl, timeoutMs, fetch })` — `fetch` is injectable, so tests never touch the network.

## Recognition API

```js
const result = await client.recognize({
  type: 'hcaptcha',
  task: 'Select all bicycles',
  imageData: ['<BASE64_TILE_1>', '<BASE64_TILE_2>'], // or imageUrls: [...]
});
console.log(result.data); // one boolean per tile, in reading order
```

Use `type: 'hcaptcha_area_select'` with exactly one image for point challenges (`result.data` is a `{x, y, w, h}` box, `result.points` lists the points). For drag-and-drop and enterprise challenges, pass the full challenge form: `client.recognize({ data: { request_type: 'image_drag_drop', ... } })`.

One recognition costs **$0.0003**, charged only when answered.

## Errors

Every non-2xx response has the same shape: `{"error": {code, message, param, request_id}}`. The SDK throws typed exceptions — `AuthenticationError` (401), `InsufficientCredits` (402), `RateLimited` (429, with `retryAfter`; honour `Retry-After`), `NinetileError` for everything else — each carrying `code`, `status` and `requestId` (quote `requestId`, or the `X-Request-Id` response header, when you contact support). A solve that was accepted can still end without a token: `SolveFailed` — never an HTTP error, and never charged. Polling past your deadline raises `SolveTimeout`.

## Status and support

`GET https://api.ninetile.io/v1/status` is a public liveness check. Docs: [ninetile.io/docs](https://ninetile.io/docs) · API reference: [create-solve](https://ninetile.io/docs/api-reference/create-solve) · Dashboard: [ninetile.io/dashboard](https://ninetile.io/dashboard)
