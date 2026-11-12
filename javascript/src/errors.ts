/** Errors raised by the ninetile client.
 *
 * Request errors (non-2xx) come from the API error envelope
 * `{"error": {code, message, param, request_id}}` and carry `code`, the HTTP
 * `status` and the `requestId` (also in the response's `X-Request-Id` header).
 */

export interface NinetileErrorOptions {
  code?: string;
  status?: number;
  requestId?: string;
}

export class NinetileError extends Error {
  code?: string;
  status?: number;
  requestId?: string;

  constructor(message: string, options: NinetileErrorOptions = {}) {
    super(message);
    this.name = 'NinetileError';
    this.code = options.code;
    this.status = options.status;
    this.requestId = options.requestId;
  }
}

/** 401: the API key is missing, malformed, unknown or revoked. */
export class AuthenticationError extends NinetileError {
  constructor(message: string, options: NinetileErrorOptions = {}) {
    super(message, options);
    this.name = 'AuthenticationError';
  }
}

/** 402: the balance (or the key's own spend limit) does not cover the call. */
export class InsufficientCredits extends NinetileError {
  constructor(message: string, options: NinetileErrorOptions = {}) {
    super(message, options);
    this.name = 'InsufficientCredits';
  }
}

export interface RateLimitedOptions extends NinetileErrorOptions {
  /** Seconds to wait, from the response's `Retry-After` header. */
  retryAfter?: number;
}

/** 429: an account, sitekey or IP rate limit was hit. Carries `retryAfter`. */
export class RateLimited extends NinetileError {
  retryAfter?: number;

  constructor(message: string, options: RateLimitedOptions = {}) {
    super(message, options);
    this.name = 'RateLimited';
    this.retryAfter = options.retryAfter;
  }
}

export interface SolveFailedOptions extends NinetileErrorOptions {
  retryable?: boolean;
  reason?: string | null;
}

/** The solve ended without a token (status failed / cancelled / expired).
 *
 * Carries `retryable` and `reason` from the solve's error object. Only retry
 * when `retryable` is true; failed work is never charged.
 */
export class SolveFailed extends NinetileError {
  retryable: boolean;
  reason: string | null;

  constructor(message: string, options: SolveFailedOptions = {}) {
    super(message, options);
    this.name = 'SolveFailed';
    this.retryable = Boolean(options.retryable);
    this.reason = options.reason ?? null;
  }
}

/** The client-side deadline passed while waiting for the solve to finish. */
export class SolveTimeout extends NinetileError {
  constructor(message: string, options: NinetileErrorOptions = {}) {
    super(message, { code: 'timeout', ...options });
    this.name = 'SolveTimeout';
  }
}
