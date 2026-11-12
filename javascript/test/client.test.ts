import { describe, expect, it } from 'vitest';
import {
  AuthenticationError,
  InsufficientCredits,
  NinetileClient,
  RateLimited,
  SolveFailed,
} from '../src/index';

function solvedPayload(status = 'solved', extra: Record<string, unknown> = {}) {
  const solved = status === 'solved';
  return {
    id: 'solve_1',
    object: 'solve',
    type: 'hcaptcha',
    status,
    token: solved ? 'P1_' + 'a'.repeat(500) : null,
    user_agent: solved ? 'Mozilla/5.0 fake' : null,
    error: null,
    charged_usd: solved ? 0.00075 : null,
    ...extra,
  };
}

function jsonResponse(status: number, payload: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

/** Returns queued responses in order; records every call. No network. */
function fakeFetch(responses: Response[]) {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fetchImpl = (async (input: any, init?: any) => {
    calls.push({ url: String(input), init: init ?? {} });
    const next = responses.shift();
    if (!next) throw new Error('fakeFetch: no queued response');
    return next;
  }) as typeof fetch;
  return { fetchImpl, calls };
}

const KEY = 'nt_live_' + 'k'.repeat(32);
const SITEKEY = '00000000-0000-0000-0000-000000000000';
const URL = 'https://target.example/login';

function makeClient(responses: Response[], options: Record<string, unknown> = {}) {
  const { fetchImpl, calls } = fakeFetch(responses);
  const client = new NinetileClient({ apiKey: KEY, fetch: fetchImpl, ...options });
  return { client, calls };
}

describe('NinetileClient', () => {
  it('throws immediately without an API key', () => {
    const saved = process.env.NT_API_KEY;
    delete process.env.NT_API_KEY;
    try {
      expect(() => new NinetileClient()).toThrow(AuthenticationError);
    } finally {
      if (saved !== undefined) process.env.NT_API_KEY = saved;
    }
  });

  it('solves successfully (200)', async () => {
    const { client, calls } = makeClient([
      jsonResponse(200, solvedPayload(), { 'X-Request-Id': 'req-200' }),
    ]);
    const solve = await client.solve(SITEKEY, URL);
    expect(solve.status).toBe('solved');
    expect(solve.token).toMatch(/^P1_/);
    expect(solve.userAgent).toBe('Mozilla/5.0 fake');
    expect(solve.raw.charged_usd).toBe(0.00075);
    expect(calls).toHaveLength(1);
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].url).toBe('https://api.ninetile.io/v1/solves');
    expect(JSON.parse(String(calls[0].init.body)).sitekey).toBe(SITEKEY);
  });

  it('polls 202 -> 202 -> 200', async () => {
    const { client, calls } = makeClient([
      jsonResponse(202, solvedPayload('pending'), { 'X-Request-Id': 'req-poll' }),
      jsonResponse(202, solvedPayload('solving')),
      jsonResponse(200, solvedPayload('solved')),
    ]);
    const solve = await client.solve(SITEKEY, URL, { pollIntervalMs: 10, timeoutMs: 5000 });
    expect(solve.status).toBe('solved');
    expect(calls.map((c) => c.init.method)).toEqual(['POST', 'GET', 'GET']);
    expect(calls[1].url).toBe('https://api.ninetile.io/v1/solves/solve_1');
  });

  it('raises InsufficientCredits on 402 and never retries the create', async () => {
    const { client, calls } = makeClient([
      jsonResponse(402, { error: { code: 'insufficient_credits', message: 'The balance does not cover this call.', param: null, request_id: 'req-402' } }, { 'X-Request-Id': 'req-402' }),
    ]);
    await expect(client.solve(SITEKEY, URL)).rejects.toMatchObject({
      name: 'InsufficientCredits',
      code: 'insufficient_credits',
      status: 402,
      requestId: 'req-402',
    });
    expect(calls).toHaveLength(1);
  });

  it('raises RateLimited with retryAfter on 429 and performs zero retries on create', async () => {
    const { client, calls } = makeClient([
      jsonResponse(429, { error: { code: 'rate_limited', message: 'Too many requests.', param: null, request_id: 'req-429' } }, { 'Retry-After': '17', 'X-Request-Id': 'req-429' }),
    ]);
    const err = await client.solve(SITEKEY, URL).then(
      () => { throw new Error('expected RateLimited'); },
      (e) => e,
    );
    expect(err).toBeInstanceOf(RateLimited);
    expect(err.retryAfter).toBe(17);
    expect(err.status).toBe(429);
    expect(err.requestId).toBe('req-429');
    expect(calls).toHaveLength(1);
  });

  it('raises SolveFailed with retryable/reason on a failed solve', async () => {
    const { client } = makeClient([
      jsonResponse(200, solvedPayload('failed', {
        error: {
          code: 'challenge_not_loaded',
          message: 'hCaptcha did not serve a challenge.',
          reason: 'sitekey_rate_limited',
          retryable: true,
          docs_url: null,
        },
      }), { 'X-Request-Id': 'req-fail' }),
    ]);
    const err = await client.solve(SITEKEY, URL).then(
      () => { throw new Error('expected SolveFailed'); },
      (e) => e,
    );
    expect(err).toBeInstanceOf(SolveFailed);
    expect(err.retryable).toBe(true);
    expect(err.reason).toBe('sitekey_rate_limited');
    expect(err.code).toBe('challenge_not_loaded');
    expect(err.requestId).toBe('req-fail');
  });

  it('honours Retry-After while polling and still solves', async () => {
    const { client, calls } = makeClient([
      jsonResponse(202, solvedPayload('pending')),
      jsonResponse(429, { error: { code: 'rate_limited', message: 'Slow down.', param: null, request_id: 'req-p429' } }, { 'Retry-After': '0' }),
      jsonResponse(200, solvedPayload('solved')),
    ]);
    const solve = await client.solve(SITEKEY, URL, { pollIntervalMs: 10, timeoutMs: 5000 });
    expect(solve.status).toBe('solved');
    expect(calls).toHaveLength(3);
  });

  it('recognize sends the simple form and maps image_data', async () => {
    const { client, calls } = makeClient([
      jsonResponse(200, { id: 'rec_1', data: [true, false], charged_usd: 0.0003 }),
    ]);
    const result = await client.recognize({ type: 'hcaptcha', task: 'Select all bicycles', imageData: ['aW1n'] });
    expect(result.id).toBe('rec_1');
    expect(result.data).toEqual([true, false]);
    const sent = JSON.parse(String(calls[0].init.body));
    expect(sent).toEqual({ type: 'hcaptcha', task: 'Select all bicycles', image_data: ['aW1n'] });
  });

  it('recognize sends the full form for drag challenges', async () => {
    const { client, calls } = makeClient([
      jsonResponse(200, { id: 'rec_2', data: [{ x: 10, y: 20, w: 5, h: 5 }], charged_usd: 0.0003 }),
    ]);
    const data = { request_type: 'image_drag_drop', requester_question: { en: 'Drag the piece' }, tasklist: [{ task_key: 't0', datapoint_uri: 'data:image/png;base64,aW1n' }] };
    const result = await client.recognize({ data });
    expect(result.id).toBe('rec_2');
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ data });
  });
});
