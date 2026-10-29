# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.settings import api_settings

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.authentication.rate_limit import AuthenticationThrottle
from plane.db.models import User
from plane.tests.contract.app import test_authentication as upstream_auth


pytestmark = [pytest.mark.contract, pytest.mark.django_db]
django_client = upstream_auth.django_client
setup_instance = upstream_auth.setup_instance

ENDPOINTS = ["sign-in", "space-sign-in", "sign-up", "space-sign-up"]
PASSWORD = "Birdplane-test-password-123!"


@pytest.fixture(autouse=True)
def auth_throttle_state(monkeypatch, settings):
    """Use upstream's scoped cleanup without clearing unrelated cache state."""
    cache.delete_pattern("throttle_authentication_*")
    monkeypatch.setattr(AuthenticationThrottle, "rate", "2/minute")
    # Freeze the window so slow CI cannot expire attempts mid-test.
    monkeypatch.setattr(AuthenticationThrottle, "timer", staticmethod(lambda: 1000.0))
    settings.WEB_URL = "https://web.birdplane.test"
    settings.APP_BASE_URL = "https://app.birdplane.test"
    settings.SPACE_BASE_URL = "https://space.birdplane.test"
    settings.SPACE_BASE_PATH = "/spaces/"
    yield
    cache.delete_pattern("throttle_authentication_*")


@pytest.fixture
def credentials(db):
    user = User.objects.create(email="rate-limit@plane.so")
    user.set_password(PASSWORD)
    user.save()
    return {"email": user.email, "password": PASSWORD}


def assert_processed(response):
    assert response.status_code == 302
    assert "RATE_LIMIT_EXCEEDED" not in response.url


def assert_throttled(response):
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.url).query)
    assert query["error_code"] == [str(AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"])]
    assert query["error_message"] == ["RATE_LIMIT_EXCEEDED"]
    return query


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("prior_attempts", [0, 1], ids=["under-limit", "at-limit"])
def test_password_auth_succeeds_through_limit(django_client, setup_instance, credentials, endpoint, prior_attempts):
    """Valid credentials establish a session both before and exactly at the limit."""
    url = reverse(endpoint)
    for _ in range(prior_attempts):
        response = django_client.post(url, {})
        assert_processed(response)
        assert "_auth_user_id" not in django_client.session

    data = credentials.copy()
    if endpoint.endswith("sign-up"):
        data["email"] = "new-rate-limit@plane.so"
    response = django_client.post(url, data)
    assert_processed(response)
    user = User.objects.get(email=data["email"])
    assert django_client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("next_path", ["/workspace/issues/", "https://evil.example", "//evil.example"])
def test_limit_plus_one_rejects_valid_credentials_with_safe_redirect(
    django_client, setup_instance, credentials, endpoint, next_path
):
    """Attempt N+1 stops before credential checking and preserves the correct origin."""
    url = reverse(endpoint)
    for _ in range(2):
        assert_processed(django_client.post(url, {}))

    data = {**credentials, "next_path": next_path}
    if endpoint.endswith("sign-up"):
        data["email"] = "blocked-new-user@plane.so"
    with patch("plane.authentication.provider.credentials.email.EmailProvider.authenticate") as authenticate:
        response = django_client.post(url, data)
    authenticate.assert_not_called()
    query = assert_throttled(response)
    target = urlsplit(response.url)
    assert target.scheme == "https"
    assert target.netloc == ("space.birdplane.test" if endpoint.startswith("space-") else "app.birdplane.test")
    assert target.path == ("/spaces/" if endpoint.startswith("space-") else "/")
    if next_path == "/workspace/issues/":
        assert query["next_path"] == [next_path]
    else:
        assert "next_path" not in query
    assert "_auth_user_id" not in django_client.session
    if endpoint.endswith("sign-up"):
        assert not User.objects.filter(email=data["email"]).exists()


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("identity_header", ["REMOTE_ADDR", "HTTP_X_FORWARDED_FOR"])
def test_different_client_identity_has_independent_budget(django_client, setup_instance, endpoint, identity_header):
    """A distinct remote IP or XFF string gets two attempts after the first is exhausted."""
    url = reverse(endpoint)
    first = {identity_header: "192.0.2.10"}
    second = {identity_header: "192.0.2.11"}
    for _ in range(2):
        assert_processed(django_client.post(url, {}, **first))
    assert_throttled(django_client.post(url, {}, **first))
    for _ in range(2):
        assert_processed(django_client.post(url, {}, **second))
    assert_throttled(django_client.post(url, {}, **second))


def test_unset_num_proxies_keys_on_whole_x_forwarded_for_string():
    """With NUM_PROXIES unset DRF uses the whole XFF chain (minus whitespace), not just the client IP."""
    assert api_settings.NUM_PROXIES is None
    factory = RequestFactory()
    throttle = AuthenticationThrottle()
    first = factory.post("/", HTTP_X_FORWARDED_FOR="192.0.2.10, 198.51.100.1", REMOTE_ADDR="203.0.113.1")
    second = factory.post("/", HTTP_X_FORWARDED_FOR="192.0.2.10, 198.51.100.2", REMOTE_ADDR="203.0.113.1")
    first.user = AnonymousUser()
    second.user = AnonymousUser()
    assert throttle.get_ident(first) == "192.0.2.10,198.51.100.1"
    assert throttle.get_ident(second) == "192.0.2.10,198.51.100.2"
    assert throttle.get_cache_key(first, None) != throttle.get_cache_key(second, None)
