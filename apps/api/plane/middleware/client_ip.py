# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Opt-in client identity for a proxy that overwrites the configured header.

The operator must ensure every path to the API passes through that proxy.
Missing/malformed trusted headers deliberately fail open to upstream identity
handling, preserving availability and compatibility with other deployments.
"""

from ipaddress import IPv6Address, ip_address, ip_network

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


# Fetched 2026-10-29 with curl from https://www.cloudflare.com/ips-v4 and
# https://www.cloudflare.com/ips-v6. Refresh when Cloudflare changes its ranges.
CLOUDFLARE_NETWORKS = tuple(
    ip_network(cidr)
    for cidr in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)


def _parse_ip(value):
    try:
        # Zone identifiers are local interface names, not client identities.
        if not isinstance(value, str) or "%" in value:
            return None
        address = ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


class ClientIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        header = settings.TRUSTED_PROXY_CLIENT_IP_HEADER.strip()
        self.header = "HTTP_" + header.upper().replace("-", "_") if header else None
        self.trust_cloudflare = settings.TRUST_CLOUDFLARE_CLIENT_IP
        self.cloudflare_networks = CLOUDFLARE_NETWORKS
        # Parse overrides once per middleware instance, never per request.
        override = settings.CLOUDFLARE_IP_RANGES.strip()
        if self.header and self.trust_cloudflare and override:
            try:
                self.cloudflare_networks = tuple(ip_network(cidr.strip()) for cidr in override.split(","))
            except ValueError as exc:
                raise ImproperlyConfigured("CLOUDFLARE_IP_RANGES must contain comma-separated CIDRs") from exc

    def __call__(self, request):
        peer = _parse_ip(request.META.get(self.header)) if self.header else None
        if peer is not None:
            client = peer
            if self.trust_cloudflare and any(peer in network for network in self.cloudflare_networks):
                client = _parse_ip(request.META.get("HTTP_CF_CONNECTING_IP")) or peer
            request.META["BIRDPLANE_ORIGINAL_REMOTE_ADDR"] = request.META.get("REMOTE_ADDR")
            request.META["BIRDPLANE_ORIGINAL_X_FORWARDED_FOR"] = request.META.get("HTTP_X_FORWARDED_FOR")
            request.META["REMOTE_ADDR"] = str(client)
            request.META["HTTP_X_FORWARDED_FOR"] = str(client)
        return self.get_response(request)
