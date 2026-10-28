# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reject binary compression codecs supplied as JSON character sets."""

import bz2
import io
import json
import zlib

import pytest
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


@pytest.mark.unit
@pytest.mark.parametrize("encoding,compress", [("bz2_codec", bz2.compress), ("zlib_codec", zlib.compress)])
def test_json_parser_rejects_compression_codecs(encoding, compress):
    # Keep the probe bounded while exercising the amplification path from
    # CVE-2026-114136. Even valid compressed JSON must never be decoded here.
    payload = json.dumps({"text": "a" * 65536}).encode()
    with pytest.raises(ParseError):
        JSONParser().parse(io.BytesIO(compress(payload)), parser_context={"encoding": encoding})


@pytest.mark.unit
def test_json_parser_accepts_utf8():
    payload = {"text": "Birdplane"}
    assert JSONParser().parse(
        io.BytesIO(json.dumps(payload).encode()), parser_context={"encoding": "utf-8"}
    ) == payload
