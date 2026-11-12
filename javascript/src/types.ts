/** Result and option types for the ninetile client. */

export interface SolveResponse {
  id: string;
  status: string;
  token: string | null;
  user_agent: string | null;
  error: { code?: string; message?: string; reason?: string | null; retryable?: boolean; docs_url?: string | null } | null;
  charged_usd?: number | null;
  [key: string]: unknown;
}

export interface SolveResult {
  id: string;
  status: string;
  token: string | null;
  userAgent: string | null;
  /** The decoded JSON response from the API. */
  raw: SolveResponse;
}

export interface SolveOptions {
  /** Hold the create request open server-side for up to N seconds (1-90). */
  wait?: number;
  /** Initial poll interval in ms; doubles each poll, capped at 10s. Default 2000. */
  pollIntervalMs?: number;
  /** Client-side deadline in ms while waiting for the solve. Default 180000. */
  timeoutMs?: number;
  /** Extra fields merged into the request body (`type`, `rqdata`, `proxy`, ...). */
  [extra: string]: unknown;
}

export interface RecognizeSimpleOptions {
  /** `hcaptcha` (grid) or `hcaptcha_area_select` (point). Default `hcaptcha`. */
  type?: string;
  /** The challenge instruction, e.g. "Select all bicycles". */
  task: string;
  /** 1-27 base64 tiles in reading order. */
  imageData?: string[];
  /** hCaptcha image URLs, instead of `imageData`. */
  imageUrls?: string[];
  /** 1-3 example images for challenges that show them. */
  imageExamples?: string[];
  data?: undefined;
  [extra: string]: unknown;
}

export interface RecognizeFullOptions {
  /** Full challenge object (`request_type`, `requester_question`, `tasklist`). Required for drag-and-drop. */
  data: Record<string, unknown>;
  [extra: string]: unknown;
}

export type RecognizeOptions = RecognizeSimpleOptions | RecognizeFullOptions;

export interface RecognizeResult {
  id: string;
  /** One boolean per tile (grid), a `{x, y, w, h}` box (area select), or one box per piece (drag). */
  data: unknown;
  points?: unknown;
  chargedUsd?: number;
  /** The decoded JSON response from the API. */
  raw: Record<string, unknown>;
}

export interface GetSolveOptions {
  /** Hold the request open server-side for up to N seconds (1-90). */
  wait?: number;
}
