"""Run inside the API container; use only synthetic keys and a private memory cache."""

import argparse
import json
import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

from django.conf import settings  # noqa: E402
from django.core.cache.backends.locmem import LocMemCache  # noqa: E402

from plane.api.rate_limit import ApiKeyRateThrottle  # noqa: E402


def verify(expected_rate):
    if settings.API_KEY_RATE_LIMIT != expected_rate:
        raise RuntimeError(f"Settings rate {settings.API_KEY_RATE_LIMIT!r} differs from {expected_rate!r}")

    throttle = ApiKeyRateThrottle()
    if throttle.rate != expected_rate:
        raise RuntimeError(f"Loaded throttle rate {throttle.rate!r} differs from {expected_rate!r}")

    # Replacing this instance's cache never touches production Redis or real API keys.
    throttle.cache = LocMemCache(f"birdplane-rate-verification-{uuid4()}", {})
    now = [1000.0]
    throttle.timer = lambda: now[0]
    first = SimpleNamespace(headers={"X-Api-Key": "synthetic-first"}, META={})
    second = SimpleNamespace(headers={"X-Api-Key": "synthetic-second"}, META={})

    for index in range(throttle.num_requests):
        if not throttle.allow_request(first, None):
            raise RuntimeError(f"Request {index + 1} was rejected before the configured limit")
        if first.META["X-RateLimit-Remaining"] != throttle.num_requests - index - 1:
            raise RuntimeError("Remaining-request header disagrees with the throttle")

    if throttle.allow_request(first, None) or throttle.wait() != throttle.duration:
        raise RuntimeError("The request above the limit must be rejected with a full-window wait")
    if not throttle.allow_request(second, None):
        raise RuntimeError("A second API key must have an independent allowance")
    now[0] += throttle.duration
    if not throttle.allow_request(first, None):
        raise RuntimeError("The first key must be allowed again after the window expires")

    return {
        "settings_rate": settings.API_KEY_RATE_LIMIT,
        "throttle_rate": throttle.rate,
        "requests_per_key": throttle.num_requests,
        "window_seconds": throttle.duration,
        "checks": ["request allowance", "remaining header", "limit and wait", "key isolation", "window expiry"],
        "cache": "isolated process-local memory",
        "production_http_requests": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", default="300/minute")
    print(json.dumps(verify(parser.parse_args().expect), sort_keys=True))
