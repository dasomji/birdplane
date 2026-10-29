# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from ipaddress import ip_address

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from rest_framework.throttling import AnonRateThrottle

from plane.middleware.client_ip import CLOUDFLARE_NETWORKS, ClientIPMiddleware
from plane.utils.ip_address import get_client_ip

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def proxy_settings(settings):
    settings.TRUSTED_PROXY_CLIENT_IP_HEADER = "X-Real-Ip"
    settings.TRUST_CLOUDFLARE_CLIENT_IP = True
    settings.CLOUDFLARE_IP_RANGES = ""


def request_with_headers(**headers):
    return RequestFactory().get(
        "/", REMOTE_ADDR="10.0.1.20", HTTP_X_FORWARDED_FOR="172.71.164.187, 10.0.1.10", **headers
    )


@pytest.mark.parametrize("header", ["", "   "])
def test_unconfigured_is_noop(settings, header):
    settings.TRUSTED_PROXY_CLIENT_IP_HEADER = header
    request = request_with_headers(HTTP_X_REAL_IP="172.71.164.187", HTTP_CF_CONNECTING_IP="192.0.2.1")
    original = request.META.copy()
    ClientIPMiddleware(lambda r: r)(request)
    assert request.META == original


@pytest.mark.parametrize("peer", [None, "", "invalid", "192.0.2.1, 192.0.2.2", "fe80::1%eth0"])
def test_missing_or_invalid_trusted_header_is_noop(peer):
    request = request_with_headers(HTTP_X_REAL_IP=peer, HTTP_CF_CONNECTING_IP="192.0.2.1")
    original = request.META.copy()
    ClientIPMiddleware(lambda r: r)(request)
    assert request.META == original


@pytest.mark.parametrize(
    "peer,cf,trust,expected",
    [
        ("172.71.164.187", "192.0.2.1", True, "192.0.2.1"),
        ("172.71.164.187", None, True, "172.71.164.187"),
        ("172.71.164.187", "invalid", True, "172.71.164.187"),
        ("198.51.100.1", "192.0.2.1", True, "198.51.100.1"),
        ("172.71.164.187", "192.0.2.1", False, "172.71.164.187"),
        ("172.71.164.187", "2001:db8:0:0::123", True, "2001:db8::123"),
        ("2606:4700::1", "2001:db8::123", True, "2001:db8::123"),
        ("::ffff:172.71.164.187", "::ffff:192.0.2.1", True, "192.0.2.1"),
        ("::ffff:198.51.100.1", "192.0.2.1", True, "198.51.100.1"),
    ],
)
def test_resolved_identity_reaches_all_readers(settings, peer, cf, trust, expected):
    settings.TRUST_CLOUDFLARE_CLIENT_IP = trust
    request = request_with_headers(HTTP_X_REAL_IP=peer, HTTP_CF_CONNECTING_IP=cf)
    original = request.META.copy()
    assert ClientIPMiddleware(lambda r: r)(request) is request
    assert request.META["REMOTE_ADDR"] == expected
    assert request.META["HTTP_X_FORWARDED_FOR"] == expected
    assert request.META["BIRDPLANE_ORIGINAL_REMOTE_ADDR"] == original["REMOTE_ADDR"]
    assert request.META["BIRDPLANE_ORIGINAL_X_FORWARDED_FOR"] == original["HTTP_X_FORWARDED_FOR"]
    assert get_client_ip(request) == expected
    assert AnonRateThrottle().get_ident(request) == expected


@pytest.mark.parametrize("edge", ["172.71.164.187", "162.158.95.208", "104.23.239.99", "172.70.248.84"])
def test_observed_edges_are_in_published_ranges(edge):
    assert any(ip_address(edge) in network for network in CLOUDFLARE_NETWORKS)


@pytest.mark.parametrize("peer,expected", [("198.51.100.1", "192.0.2.1"), ("172.71.164.187", "172.71.164.187")])
def test_range_override_replaces_embedded_ranges(settings, peer, expected):
    settings.CLOUDFLARE_IP_RANGES = "198.51.100.0/24, 2001:db8::/32"
    request = request_with_headers(HTTP_X_REAL_IP=peer, HTTP_CF_CONNECTING_IP="192.0.2.1")
    ClientIPMiddleware(lambda r: r)(request)
    assert get_client_ip(request) == expected


def test_invalid_range_override_rejected(settings):
    settings.CLOUDFLARE_IP_RANGES = "not-a-cidr"
    with pytest.raises(ImproperlyConfigured, match="CLOUDFLARE_IP_RANGES"):
        ClientIPMiddleware(lambda r: r)


def test_missing_original_values_preserved():
    request = RequestFactory().get("/", HTTP_X_REAL_IP="198.51.100.1")
    del request.META["REMOTE_ADDR"]
    ClientIPMiddleware(lambda r: r)(request)
    assert request.META["BIRDPLANE_ORIGINAL_REMOTE_ADDR"] is None
    assert request.META["BIRDPLANE_ORIGINAL_X_FORWARDED_FOR"] is None
