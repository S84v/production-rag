import ipaddress
import math
import time

from fastapi import HTTPException, Request

RATE_LIMIT_MESSAGE = "Too many requests. Please try again later."


class RateLimiter:
    """In-memory fixed-window rate limiter keyed by client.

    Each client gets ``limit`` requests per ``window_seconds`` window, anchored
    at their first request. State is per process: it is bounded by
    ``max_clients`` and expired entries are pruned, so it cannot grow without
    limit. This is best-effort abuse control, not a global spending cap.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        max_clients: int = 10_000,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._max_clients = max_clients
        # client key -> (window_start, count)
        self._counters: dict[str, tuple[float, int]] = {}

    @property
    def tracked_clients(self) -> int:
        """Number of client counters currently held in memory."""
        return len(self._counters)

    def check(self, client: str, now: float | None = None) -> int:
        """Record a request and return whole seconds to wait (0 when allowed).

        The check is synchronous with no ``await``, so within the application's
        event loop it cannot interleave with another request. Rejected requests
        do not extend the window.
        """
        now = time.monotonic() if now is None else now

        self._expire(now)

        window_start, count = self._counters.get(client, (now, 0))

        if now - window_start >= self._window:
            window_start, count = now, 0

        if count >= self._limit:
            return max(1, math.ceil(self._window - (now - window_start)))

        self._counters[client] = (window_start, count + 1)

        return 0

    def _expire(self, now: float) -> None:
        if len(self._counters) < self._max_clients:
            return

        for key in [
            key
            for key, (window_start, _) in self._counters.items()
            if now - window_start >= self._window
        ]:
            del self._counters[key]

        # If the map is still full, every tracked client is active: evict the
        # oldest window so memory stays bounded.
        while len(self._counters) >= self._max_clients:
            oldest = min(self._counters, key=lambda key: self._counters[key][0])
            del self._counters[oldest]


def client_key(request: Request, *, trust_cloud_run_x_forwarded_for: bool) -> str:
    """Return a stable client key for rate limiting.

    By default the direct TCP peer (``request.client.host``) is used. It cannot
    be spoofed by request headers, but behind a proxy it is the proxy address,
    so the limit becomes per instance rather than per end user.

    ``trust_cloud_run_x_forwarded_for`` opts into reading the client IP from the
    ``X-Forwarded-For`` chain. That is only safe for verified direct Cloud Run
    ingress, where the proxy appends the real client IP as the trusted suffix of
    the chain: earlier entries are client-supplied and ignored. The candidate
    must parse as an IP address, otherwise the direct peer is used.
    """
    if trust_cloud_run_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")

        if forwarded:
            candidate = forwarded.split(",")[-1].strip()

            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass

    client = request.client

    return client.host if client is not None else "unknown"


def enforce_rate_limit(
    limiter: RateLimiter,
    request: Request,
    *,
    trust_cloud_run_x_forwarded_for: bool = False,
) -> None:
    """Raise ``429`` with ``Retry-After`` when the client is over the limit."""
    retry_after = limiter.check(
        client_key(
            request,
            trust_cloud_run_x_forwarded_for=trust_cloud_run_x_forwarded_for,
        )
    )

    if retry_after:
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMIT_MESSAGE,
            headers={"Retry-After": str(retry_after)},
        )
