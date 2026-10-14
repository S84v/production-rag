import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from production_rag.api.rate_limit import (
    RATE_LIMIT_MESSAGE,
    RateLimiter,
    client_key,
    enforce_rate_limit,
)


def make_request(headers=None, client=("10.0.0.1", 1234)):
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]

    return Request(
        {
            "type": "http",
            "headers": raw_headers,
            "client": client,
        }
    )


def test_allows_up_to_limit_then_rejects():
    limiter = RateLimiter(limit=3, window_seconds=60.0)

    assert [limiter.check("a", now=0.0) for _ in range(3)] == [0, 0, 0]
    assert limiter.check("a", now=0.0) == 60


def test_retry_after_counts_down_and_resets_after_window():
    limiter = RateLimiter(limit=1, window_seconds=60.0)

    assert limiter.check("a", now=0.0) == 0
    assert limiter.check("a", now=30.0) == 30
    assert limiter.check("a", now=59.999) == 1
    # Once the window elapses the client is allowed again.
    assert limiter.check("a", now=60.0) == 0


def test_rejected_requests_do_not_extend_window():
    limiter = RateLimiter(limit=1, window_seconds=60.0)

    limiter.check("a", now=0.0)

    assert limiter.check("a", now=10.0) == 50
    assert limiter.check("a", now=20.0) == 40


def test_clients_are_isolated():
    limiter = RateLimiter(limit=1, window_seconds=60.0)

    assert limiter.check("a", now=0.0) == 0
    assert limiter.check("b", now=0.0) == 0
    assert limiter.check("a", now=0.0) == 60


def test_state_is_bounded_and_expired_entries_pruned():
    limiter = RateLimiter(limit=5, window_seconds=10.0, max_clients=3)

    for index in range(6):
        limiter.check(f"client-{index}", now=float(index))

    assert limiter.tracked_clients <= 3

    # After the window elapses, stale entries are pruned on the next check.
    limiter.check("fresh", now=1000.0)

    assert limiter.tracked_clients == 1


@pytest.mark.asyncio
async def test_simultaneous_checks_respect_the_limit():
    limiter = RateLimiter(limit=5, window_seconds=60.0)

    async def hit() -> int:
        return limiter.check("a", now=0.0)

    results = await asyncio.gather(*(hit() for _ in range(20)))

    assert sum(1 for retry_after in results if retry_after == 0) == 5


def test_client_key_defaults_to_direct_peer():
    request = make_request(
        headers={"x-forwarded-for": "1.2.3.4"},
        client=("10.0.0.1", 1234),
    )

    assert client_key(request, trust_cloud_run_x_forwarded_for=False) == "10.0.0.1"


def test_client_key_uses_last_forwarded_entry_when_trusted():
    request = make_request(
        headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
        client=("10.0.0.1", 1),
    )

    assert client_key(request, trust_cloud_run_x_forwarded_for=True) == "5.6.7.8"


def test_client_key_ignores_spoofed_earlier_entries():
    request = make_request(
        headers={"x-forwarded-for": "9.9.9.9, 203.0.113.7"},
        client=("10.0.0.1", 1),
    )

    assert client_key(request, trust_cloud_run_x_forwarded_for=True) == "203.0.113.7"


def test_client_key_normalizes_valid_ipv6_suffix():
    request = make_request(
        headers={"x-forwarded-for": "2001:db8::1"},
        client=("10.0.0.1", 1),
    )

    assert client_key(request, trust_cloud_run_x_forwarded_for=True) == "2001:db8::1"


def test_client_key_falls_back_when_forwarded_header_is_missing():
    request = make_request(client=("10.0.0.1", 1))

    assert client_key(request, trust_cloud_run_x_forwarded_for=True) == "10.0.0.1"


def test_client_key_falls_back_when_forwarded_header_is_malformed():
    request = make_request(
        headers={"x-forwarded-for": "not-an-ip"},
        client=("10.0.0.1", 1),
    )

    assert client_key(request, trust_cloud_run_x_forwarded_for=True) == "10.0.0.1"


def test_client_key_handles_missing_direct_peer():
    request = make_request(client=None)

    assert client_key(request, trust_cloud_run_x_forwarded_for=False) == "unknown"


def test_enforce_rate_limit_raises_429_with_retry_after():
    limiter = RateLimiter(limit=1, window_seconds=60.0)
    request = make_request(client=("10.0.0.1", 1))

    enforce_rate_limit(limiter, request)

    with pytest.raises(HTTPException) as excinfo:
        enforce_rate_limit(limiter, request)

    assert excinfo.value.status_code == 429
    assert excinfo.value.detail == RATE_LIMIT_MESSAGE
    assert excinfo.value.headers == {"Retry-After": "60"}
