/** Small client for the Ninetile API (https://ninetile.io/docs).
 * Failed solves are never charged. `POST /v1/solves` is never retried: a retry is a
 * brand-new solve (and charge). Only polling `GET /v1/solves/{id}` is retried, which is free. */

import {
  AuthenticationError,
  InsufficientCredits,
  NinetileError,
  RateLimited,
  SolveFailed,
  SolveTimeout,
} from './errors';
import type {
  GetSolveOptions,
  RecognizeOptions,
  RecognizeResult,
  SolveOptions,
  SolveResponse,
  SolveResult,
} from './types';

export const DEFAULT_BASE_URL = 'https://api.ninetile.io/v1';

const PENDING = new Set(['pending', 'solving']);
const MAX_POLL_DELAY_MS = 10_000;

export interface NinetileClientOptions {
  apiKey?: string;
  baseUrl?: string;
  /** Per-request timeout in ms (default 30000). */
  timeoutMs?: number;
  /** Injectable fetch implementation; defaults to the global `fetch`. */
  fetch?: typeof fetch;
}

interface RequestResult {
  body: any;
  requestId?: string;
}

export class NinetileClient {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: NinetileClientOptions = {}) {
    const apiKey = options.apiKey ?? (typeof process !== 'undefined' ? process.env?.NT_API_KEY : undefined);
    if (!apiKey) {
      throw new AuthenticationError('No API key. Pass apiKey: ... or set NT_API_KEY.', { code: 'missing_api_key' });
    }
    const fetchImpl = options.fetch ?? (typeof fetch !== 'undefined' ? fetch : undefined);
    if (!fetchImpl) {
      throw new NinetileError('No fetch implementation. Pass fetch in options (Node >= 18 has one built in).', {
        code: 'missing_fetch',
      });
    }
    this.apiKey = apiKey;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.fetchImpl = fetchImpl;
  }

  /** Solve an hCaptcha challenge; resolves once the solve is final. Throws
   * `SolveFailed` if it ends without a token. Extra option fields (`type`,
   * `rqdata`, `proxy`) are merged into the body. */
  async solve(sitekey: string, url: string, options: SolveOptions = {}): Promise<SolveResult> {
    const { wait, pollIntervalMs = 2000, timeoutMs = 180_000, ...extra } = options;
    if (wait !== undefined && (!Number.isInteger(wait) || wait < 1 || wait > 90)) {
      throw new RangeError('wait must be a whole number of seconds from 1 to 90');
    }
    const body = { type: 'hcaptcha', sitekey, url, ...extra };
    const requestTimeout = wait !== undefined ? Math.max(this.timeoutMs, wait * 1000 + 10_000) : this.timeoutMs;
    const { body: created, requestId } = await this.request('POST', '/solves', {
      params: wait !== undefined ? { wait } : undefined,
      json: body,
      timeoutMs: requestTimeout,
    });
    if (!PENDING.has(created?.status)) {
      return this.finalSolve(created, requestId);
    }
    return this.poll(created, requestId, pollIntervalMs, timeoutMs);
  }

  /** Answer a challenge synchronously via `POST /v1/recognize`. Simple form:
   * `{ type, task, imageData | imageUrls }`; full form (drag-and-drop): `{ data }`. */
  async recognize(options: RecognizeOptions): Promise<RecognizeResult> {
    const { data, type = 'hcaptcha', task, imageData, imageUrls, imageExamples, ...extra } = options as Record<
      string,
      any
    >;
    let body: Record<string, unknown>;
    if (data !== undefined) {
      body = { data, ...extra };
    } else {
      body = { type, ...extra };
      if (task !== undefined) body.task = task;
      if (imageData !== undefined) body.image_data = imageData;
      if (imageUrls !== undefined) body.image_urls = imageUrls;
      if (imageExamples !== undefined) body.image_examples = imageExamples;
    }
    const { body: raw, requestId } = await this.request('POST', '/recognize', { json: body });
    return { id: raw?.id, data: raw?.data, points: raw?.points, chargedUsd: raw?.charged_usd, raw };
  }

  /** Fetch a solve by id (202 while pending, 200 once final). */
  async getSolve(solveId: string, options: GetSolveOptions = {}): Promise<SolveResult> {
    const { body, requestId } = await this.request('GET', `/solves/${encodeURIComponent(solveId)}`, {
      params: options.wait !== undefined ? { wait: Math.trunc(options.wait) } : undefined,
    });
    return this.toSolveResult(body);
  }

  private async poll(
    solve: SolveResponse,
    requestId: string | undefined,
    pollIntervalMs: number,
    timeoutMs: number,
  ): Promise<SolveResult> {
    const deadline = Date.now() + timeoutMs;
    let delay = Math.max(500, pollIntervalMs);
    for (;;) {
      try {
        const { body, requestId: rid } = await this.request('GET', `/solves/${encodeURIComponent(solve.id)}`, {
          timeoutMs: this.timeoutMs,
        });
        solve = body;
        requestId = rid ?? requestId;
      } catch (err) {
        if (!(err instanceof RateLimited)) throw err;
        const remaining = deadline - Date.now();
        if (remaining <= 0) {
          throw new SolveTimeout(`Timed out after ${timeoutMs}ms waiting for solve ${solve.id}.`, { requestId });
        }
        const waitMs = Math.min((err.retryAfter ?? delay / 1000) * 1000, remaining);
        await sleep(waitMs);
        continue;
      }
      if (!PENDING.has(solve.status)) {
        return this.finalSolve(solve, requestId);
      }
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        throw new SolveTimeout(`Timed out after ${timeoutMs}ms waiting for solve ${solve.id}.`, { requestId });
      }
      await sleep(Math.min(delay, remaining));
      delay = Math.min(delay * 2, MAX_POLL_DELAY_MS);
    }
  }

  private finalSolve(solve: SolveResponse, requestId?: string): SolveResult {
    if (solve?.status === 'solved') {
      return this.toSolveResult(solve);
    }
    const err = solve?.error ?? {};
    throw new SolveFailed(
      err.message ?? `Solve ${solve?.id} ended with status "${solve?.status}".`,
      {
        code: err.code ?? 'solve_failed',
        status: 200,
        requestId,
        retryable: err.retryable,
        reason: err.reason ?? null,
      },
    );
  }

  private toSolveResult(raw: SolveResponse): SolveResult {
    return { id: raw.id, status: raw.status, token: raw.token ?? null, userAgent: raw.user_agent ?? null, raw };
  }

  private async request(
    method: string,
    path: string,
    opts: { params?: Record<string, unknown>; json?: unknown; timeoutMs?: number } = {},
  ): Promise<RequestResult> {
    const url = new URL(this.baseUrl + path);
    if (opts.params) {
      for (const [key, value] of Object.entries(opts.params)) {
        if (value !== undefined) url.searchParams.set(key, String(value));
      }
    }
    const timeoutMs = opts.timeoutMs ?? this.timeoutMs;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let resp: Response;
    try {
      resp = await this.fetchImpl(url.toString(), {
        method,
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          Accept: 'application/json',
          ...(opts.json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        },
        body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined,
        signal: controller.signal,
      } as RequestInit);
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        throw new NinetileError(`Request timed out after ${timeoutMs}ms.`, { code: 'timeout', status: 0 });
      }
      throw new NinetileError(`Network error: ${err?.message ?? err}`, { code: 'network_error', status: 0 });
    } finally {
      clearTimeout(timer);
    }
    const requestId = resp.headers.get('X-Request-Id') ?? undefined;
    if (resp.status < 200 || resp.status >= 300) {
      throw await this.errorFrom(resp, requestId);
    }
    try {
      return { body: await resp.json(), requestId };
    } catch {
      throw new NinetileError('The API returned a body that is not JSON.', {
        code: 'invalid_response',
        status: resp.status,
        requestId,
      });
    }
  }

  private async errorFrom(resp: Response, requestId?: string): Promise<NinetileError> {
    let err: { code?: string; message?: string } = {};
    try {
      err = ((await resp.json()) as any)?.error ?? {};
    } catch {
      // fall through to defaults
    }
    const code = err.code ?? 'internal_error';
    const message = err.message ?? `HTTP ${resp.status}`;
    const base = { code, status: resp.status, requestId };
    if (resp.status === 401) return new AuthenticationError(message, base);
    if (resp.status === 402) return new InsufficientCredits(message, base);
    if (resp.status === 429) {
      const raw = resp.headers.get('Retry-After');
      const parsed = raw ? Number.parseInt(raw, 10) : Number.NaN;
      return new RateLimited(message, { ...base, retryAfter: Number.isNaN(parsed) ? undefined : parsed });
    }
    return new NinetileError(message, base);
  }
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
