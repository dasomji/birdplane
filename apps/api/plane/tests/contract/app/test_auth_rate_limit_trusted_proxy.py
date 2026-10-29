# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.urls import reverse

from plane.tests.contract.app import test_auth_rate_limit_birdplane as auth

pytestmark = [pytest.mark.contract, pytest.mark.django_db]
django_client = auth.django_client
setup_instance = auth.setup_instance
auth_throttle_state = auth.auth_throttle_state
EDGES = ["172.71.164.187", "162.158.95.208", "104.23.239.99", "172.70.248.84"]


@pytest.fixture(autouse=True)
def trusted_proxy(settings):
    settings.TRUSTED_PROXY_CLIENT_IP_HEADER = "X-Real-Ip"
    settings.TRUST_CLOUDFLARE_CLIENT_IP = True
    settings.CLOUDFLARE_IP_RANGES = ""


def post(client, endpoint, peer, cf):
    url = "/auth/email-check/" if endpoint == "email-check" else reverse(endpoint)
    # Empty input exercises the throttle before expensive credential processing.
    return client.post(
        url,
        {},
        HTTP_X_REAL_IP=peer,
        HTTP_X_FORWARDED_FOR=f"{peer}, 10.0.1.10",
        HTTP_CF_CONNECTING_IP=cf,
        REMOTE_ADDR="10.0.1.20",
    )


def assert_result(response, endpoint, throttled=False):
    if endpoint == "email-check":
        assert response.status_code == (429 if throttled else 400)
    elif throttled:
        auth.assert_throttled(response)
    else:
        auth.assert_processed(response)


@pytest.mark.parametrize("endpoint", ["email-check", "sign-in"])
def test_rotating_edges_share_client_budget(django_client, setup_instance, endpoint):
    """A stable Cloudflare client is limited despite edge rotation; another gets its own budget."""
    for client_ip in ["2001:db8::123", "2001:db8::456"]:
        for attempt, edge in enumerate(EDGES):
            response = post(django_client, endpoint, edge, client_ip)
            assert_result(response, endpoint, throttled=attempt >= 2)


@pytest.mark.parametrize("endpoint", ["email-check", "sign-in"])
def test_direct_origin_cannot_rotate_forged_cloudflare_identity(django_client, setup_instance, endpoint):
    """A direct peer cannot escape its budget by forging a different CF header each time."""
    for attempt in range(4):
        response = post(django_client, endpoint, "198.51.100.1", f"2001:db8::{attempt + 1}")
        assert_result(response, endpoint, throttled=attempt >= 2)


@pytest.mark.parametrize("endpoint", ["email-check", "sign-in"])
def test_without_config_rotating_edges_escape_limit(settings, django_client, setup_instance, endpoint):
    """Document upstream's rotating-XFF buckets when the middleware is disabled."""
    settings.TRUSTED_PROXY_CLIENT_IP_HEADER = ""
    for edge in EDGES:
        assert_result(post(django_client, endpoint, edge, "2001:db8::123"), endpoint)
