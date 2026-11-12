"""Result objects returned by the client."""


class Solve:
    """A solve returned by ``POST /v1/solves`` (and re-read by ``GET /v1/solves/{id}``).

    ``raw`` is the decoded JSON response. ``token`` and ``user_agent`` are only
    set when ``status == "solved"``; submit the token with that exact User-Agent.
    """

    def __init__(self, client, raw, request_id=None):
        self._client = client
        self.raw = raw
        self.request_id = request_id

    @property
    def id(self):
        return self.raw.get("id")

    @property
    def status(self):
        return self.raw.get("status")

    @property
    def token(self):
        return self.raw.get("token")

    @property
    def user_agent(self):
        return self.raw.get("user_agent")

    @property
    def charged_usd(self):
        return self.raw.get("charged_usd")

    @property
    def error(self):
        return self.raw.get("error")

    def wait(self, *, poll_interval=2.0, timeout=180.0):
        """Poll ``GET /v1/solves/{id}`` until the solve is final and return self.

        Polls with exponential backoff (starting at ``poll_interval`` seconds,
        doubling, capped at 10s) and honours ``Retry-After`` on 429 responses.
        Raises :class:`SolveFailed` if the solve produced no token, and
        :class:`SolveTimeout` if ``timeout`` seconds pass first. Only valid for
        solves created with :class:`NinetileClient`; use :meth:`wait_async` on a
        :class:`AsyncNinetileClient`.
        """
        if getattr(self._client, "is_async", False):
            raise RuntimeError(
                "wait() cannot block on an async solve; use `await solve.wait_async(...)`."
            )
        return self._client._poll(self, poll_interval=poll_interval, timeout=timeout)

    async def wait_async(self, *, poll_interval=2.0, timeout=180.0):
        """Async counterpart of :meth:`wait`; same backoff, same semantics."""
        if not getattr(self._client, "is_async", False):
            raise RuntimeError(
                "wait_async() needs a solve created with AsyncNinetileClient; use wait()."
            )
        return await self._client._poll_async(self, poll_interval=poll_interval, timeout=timeout)

    def __repr__(self):
        return f"<ninetile.Solve id={self.id} status={self.status}>"


class RecognitionResult:
    """The decoded answer from ``POST /v1/recognize``.

    ``data`` is one boolean per tile in reading order (``type="hcaptcha"``),
    a ``{x, y, w, h}`` click box (``hcaptcha_area_select``), or one box per
    dragged piece. ``points`` is present for point/area answers.
    """

    def __init__(self, raw, request_id=None):
        self.raw = raw
        self.request_id = request_id

    @property
    def id(self):
        return self.raw.get("id")

    @property
    def data(self):
        return self.raw.get("data")

    @property
    def points(self):
        return self.raw.get("points")

    @property
    def charged_usd(self):
        return self.raw.get("charged_usd")

    def __repr__(self):
        return f"<ninetile.RecognitionResult id={self.id}>"
