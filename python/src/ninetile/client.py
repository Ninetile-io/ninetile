"""Client for the Ninetile API (see https://ninetile.io/docs).

One package, two surfaces: :class:`NinetileClient` (sync) and
:class:`AsyncNinetileClient` (async). Both share the same parsing, error
mapping and polling logic; the only difference is how HTTP is awaited.

Failed solves are never charged. Retry only failures the API marks ``retryable``,
and only by calling ``solve()`` again -- a retry of the create call is a brand-new
solve and, if it succeeds, a new charge. This client never silently retries
``POST /v1/solves``; the only retrying it does is polling ``GET /v1/solves/{id}``
in :meth:`Solve.wait`, which is free.
"""

import asyncio
import os
import time

import httpx

from .errors import (
    AuthenticationError,
    InsufficientCredits,
    NinetileError,
    RateLimited,
    SolveFailed,
    SolveTimeout,
)
from .models import RecognitionResult, Solve

DEFAULT_BASE_URL = "https://api.ninetile.io/v1"
_PENDING = ("pending", "solving")
_MAX_POLL_DELAY = 10.0


def _prepare_solve(sitekey, url, wait, extra):
    body = {"type": "hcaptcha", "sitekey": sitekey, "url": url, **extra}
    params = {}
    if wait is not None:
        wait = int(wait)
        if not 1 <= wait <= 90:
            raise ValueError("wait must be a whole number of seconds from 1 to 90")
        params["wait"] = wait
    return body, params, wait


def _prepare_recognize(type, task, image_data, image_urls, image_examples, data, extra):
    if data is not None:
        return {"data": data, **extra}
    body = {"type": type, **extra}
    if task is not None:
        body["task"] = task
    if image_data is not None:
        body["image_data"] = image_data
    if image_urls is not None:
        body["image_urls"] = image_urls
    if image_examples is not None:
        body["image_examples"] = image_examples
    return body


class _BaseClient:
    """Shared configuration, parsing, error mapping and poll bookkeeping."""

    is_async = False

    def __init__(self, api_key, base_url, timeout, session):
        self.api_key = api_key or os.environ.get("NT_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key. Pass api_key=... or set NT_API_KEY.",
                code="missing_api_key",
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    def _solve_from(self, resp):
        return Solve(self, resp["body"], resp["request_id"])

    def _final(self, solve):
        if solve.status == "solved":
            return solve
        err = solve.raw.get("error") or {}
        raise SolveFailed(
            err.get("message") or f"Solve {solve.id} ended with status {solve.status!r}.",
            code=err.get("code", "solve_failed"),
            status=200,
            request_id=solve.request_id,
            retryable=err.get("retryable", False),
            reason=err.get("reason"),
        )

    def _parse_response(self, resp):
        request_id = resp.headers.get("X-Request-Id")
        if not 200 <= resp.status_code < 300:
            raise self._error_from(resp, request_id)
        try:
            body = resp.json()
        except ValueError:
            raise NinetileError(
                "The API returned a body that is not JSON.",
                code="invalid_response",
                status=resp.status_code,
                request_id=request_id,
            ) from None
        return {"body": body, "request_id": request_id}

    def _error_from(self, resp, request_id):
        try:
            err = (resp.json() or {}).get("error") or {}
        except ValueError:
            err = {}
        code = err.get("code") or "internal_error"
        message = err.get("message") or f"HTTP {resp.status_code}"
        kwargs = {"code": code, "status": resp.status_code, "request_id": request_id}
        if resp.status_code == 401:
            return AuthenticationError(message, **kwargs)
        if resp.status_code == 402:
            return InsufficientCredits(message, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            try:
                retry_after = int(retry_after) if retry_after else None
            except ValueError:
                retry_after = None
            return RateLimited(message, retry_after=retry_after, **kwargs)
        return NinetileError(message, **kwargs)

    @staticmethod
    def _solve_timeout(timeout, wait):
        return max(timeout, wait + 10) if wait else timeout

    @staticmethod
    def _rate_limit_delay(exc, delay, deadline):
        sleep_for = float(exc.retry_after) if exc.retry_after else delay
        return min(sleep_for, max(0.0, deadline - time.monotonic()))

    @staticmethod
    def _poll_delay(delay):
        return min(delay * 2, _MAX_POLL_DELAY)

    @staticmethod
    def _poll_timed_out(solve, timeout, request_id):
        return SolveTimeout(
            f"Timed out after {timeout}s waiting for solve {solve.id}.",
            request_id=request_id,
        )


class NinetileClient(_BaseClient):
    """Synchronous Ninetile API client. Auth key comes from ``api_key`` or ``NT_API_KEY``."""

    def __init__(self, api_key=None, base_url=DEFAULT_BASE_URL, timeout=30.0, session=None):
        super().__init__(api_key, base_url, timeout, session or httpx.Client())

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def solve(self, sitekey, url, *, wait=None, poll_interval=2.0, timeout=180.0, **extra):
        """Solve an hCaptcha challenge; blocks until the solve is final.

        Raises :class:`SolveFailed` if the solve ends without a token. Pass
        ``wait=N`` (1-90) to hold the create request open server-side; otherwise
        this polls. Extra keyword fields (``type``, ``rqdata``, ``proxy``) are
        merged into the request body. The create call is never retried
        automatically: a retry would be a new solve, with a new charge.
        """
        body, params, wait = _prepare_solve(sitekey, url, wait, extra)
        request_timeout = self._solve_timeout(self.timeout, wait)
        resp = self._request("POST", "/solves", params=params, json=body, timeout=request_timeout)
        solve = self._solve_from(resp)
        if solve.status not in _PENDING:
            return self._final(solve)
        return self._poll(solve, poll_interval=poll_interval, timeout=timeout)

    def recognize(self, *, type="hcaptcha", task=None, image_data=None, image_urls=None,
                  image_examples=None, data=None, **extra):
        """Answer a challenge synchronously via ``POST /v1/recognize``.

        Simple form: ``type`` (``hcaptcha`` or ``hcaptcha_area_select``), ``task``
        (the instruction) and ``image_data`` (1-27 base64 tiles in reading order;
        ``image_urls`` for hCaptcha image URLs instead). Full form: pass
        ``data={...}`` with ``request_type``, ``requester_question`` and
        ``tasklist`` (required for drag-and-drop). Returns a
        :class:`RecognitionResult`; failed recognition is not charged.
        """
        body = _prepare_recognize(type, task, image_data, image_urls, image_examples, data, extra)
        resp = self._request("POST", "/recognize", json=body)
        return RecognitionResult(resp["body"], resp["request_id"])

    def get_solve(self, solve_id, *, wait=None):
        """Fetch a solve by id (202 while pending, 200 once final)."""
        params = {"wait": int(wait)} if wait else None
        return self._solve_from(self._request("GET", f"/solves/{solve_id}", params=params))

    # ---- internals ---------------------------------------------------------

    def _poll(self, solve, *, poll_interval, timeout):
        deadline = time.monotonic() + timeout
        delay = max(0.5, float(poll_interval))
        while True:
            try:
                resp = self._request("GET", f"/solves/{solve.id}", timeout=self.timeout)
            except RateLimited as exc:
                time.sleep(self._rate_limit_delay(exc, delay, deadline))
                continue
            solve = self._solve_from(resp)
            if solve.status not in _PENDING:
                return self._final(solve)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._poll_timed_out(solve, timeout, solve.request_id)
            time.sleep(min(delay, remaining))
            delay = self._poll_delay(delay)

    def _request(self, method, path, *, params=None, json=None, timeout=None):
        resp = self.session.request(
            method,
            self.base_url + path,
            params=params,
            json=json,
            headers=self._headers(),
            timeout=timeout if timeout is not None else self.timeout,
        )
        return self._parse_response(resp)


Client = NinetileClient


class AsyncNinetileClient(_BaseClient):
    """Async Ninetile API client. Auth key comes from ``api_key`` or ``NT_API_KEY``."""

    is_async = True

    def __init__(self, api_key=None, base_url=DEFAULT_BASE_URL, timeout=30.0, session=None):
        super().__init__(api_key, base_url, timeout, session or httpx.AsyncClient())

    async def aclose(self):
        await self.session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    async def solve(self, sitekey, url, *, wait=None, poll_interval=2.0, timeout=180.0, **extra):
        """Async counterpart of :meth:`NinetileClient.solve`; same semantics."""
        body, params, wait = _prepare_solve(sitekey, url, wait, extra)
        request_timeout = self._solve_timeout(self.timeout, wait)
        resp = await self._request("POST", "/solves", params=params, json=body, timeout=request_timeout)
        solve = self._solve_from(resp)
        if solve.status not in _PENDING:
            return self._final(solve)
        return await self._poll_async(solve, poll_interval=poll_interval, timeout=timeout)

    async def recognize(self, *, type="hcaptcha", task=None, image_data=None, image_urls=None,
                        image_examples=None, data=None, **extra):
        """Async counterpart of :meth:`NinetileClient.recognize`; same semantics."""
        body = _prepare_recognize(type, task, image_data, image_urls, image_examples, data, extra)
        resp = await self._request("POST", "/recognize", json=body)
        return RecognitionResult(resp["body"], resp["request_id"])

    async def get_solve(self, solve_id, *, wait=None):
        """Async counterpart of :meth:`NinetileClient.get_solve`; same semantics."""
        params = {"wait": int(wait)} if wait else None
        return self._solve_from(await self._request("GET", f"/solves/{solve_id}", params=params))

    # ---- internals ---------------------------------------------------------

    async def _poll_async(self, solve, *, poll_interval, timeout):
        deadline = time.monotonic() + timeout
        delay = max(0.5, float(poll_interval))
        while True:
            try:
                resp = await self._request("GET", f"/solves/{solve.id}", timeout=self.timeout)
            except RateLimited as exc:
                await asyncio.sleep(self._rate_limit_delay(exc, delay, deadline))
                continue
            solve = self._solve_from(resp)
            if solve.status not in _PENDING:
                return self._final(solve)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._poll_timed_out(solve, timeout, solve.request_id)
            await asyncio.sleep(min(delay, remaining))
            delay = self._poll_delay(delay)

    async def _request(self, method, path, *, params=None, json=None, timeout=None):
        resp = await self.session.request(
            method,
            self.base_url + path,
            params=params,
            json=json,
            headers=self._headers(),
            timeout=timeout if timeout is not None else self.timeout,
        )
        return self._parse_response(resp)
