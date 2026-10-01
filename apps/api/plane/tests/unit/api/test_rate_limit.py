from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.cache.backends.locmem import LocMemCache

from plane.api.rate_limit import ApiKeyRateThrottle


@pytest.fixture
def throttle(monkeypatch):
    monkeypatch.setattr(ApiKeyRateThrottle, "rate", "300/minute")
    instance = ApiKeyRateThrottle()
    instance.cache = LocMemCache(f"api-key-rate-test-{uuid4()}", {})
    instance.timer = lambda: 1000.0
    return instance


def request(key):
    return SimpleNamespace(headers={"X-Api-Key": key}, META={})


@pytest.mark.unit
def test_300_requests_allowed_then_throttled_with_wait(throttle):
    first = request("first")
    for index in range(300):
        assert throttle.allow_request(first, None)
        assert first.META["X-RateLimit-Remaining"] == 299 - index
    assert not throttle.allow_request(first, None)
    assert throttle.wait() == 60


@pytest.mark.unit
def test_api_keys_have_independent_allowances(throttle):
    first = request("first")
    for _ in range(300):
        assert throttle.allow_request(first, None)
    assert not throttle.allow_request(first, None)
    second = request("second")
    assert throttle.allow_request(second, None)
    assert second.META["X-RateLimit-Remaining"] == 299


@pytest.mark.unit
def test_allowance_recovers_at_window_boundary(throttle):
    first = request("first")
    for _ in range(300):
        assert throttle.allow_request(first, None)
    throttle.timer = lambda: 1059.0
    assert not throttle.allow_request(first, None)
    assert throttle.wait() == 1
    throttle.timer = lambda: 1060.0
    assert throttle.allow_request(first, None)
    assert first.META["X-RateLimit-Remaining"] == 299
