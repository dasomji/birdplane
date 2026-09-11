# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.filters.pql import PQLSyntaxError, parse_pql


@pytest.mark.unit
def test_parse_pql_preserves_relative_date_expression():
    assert parse_pql("createdAt >= daysAgo(7)") == {
        "created_at__gte": "daysAgo(7)",
    }


@pytest.mark.unit
def test_parse_pql_builds_and_filter_tree():
    assert parse_pql('priority = "high" AND stateGroup = "started"') == {
        "and": [
            {"priority__exact": "high"},
            {"state_group__exact": "started"},
        ]
    }


@pytest.mark.unit
def test_parse_pql_builds_or_filter_tree():
    assert parse_pql('priority = "urgent" OR priority = "high"') == {
        "or": [
            {"priority__exact": "urgent"},
            {"priority__exact": "high"},
        ]
    }


@pytest.mark.unit
def test_parse_pql_handles_parentheses_precedence_not_and_between():
    query = (
        "(createdAt = today() OR dueDate BETWEEN startOfWeek() AND endOfWeek()) "
        "AND NOT priority = High"
    )

    assert parse_pql(query) == {
        "and": [
            {
                "or": [
                    {"created_at__exact": "today()"},
                    {
                        "target_date__range": [
                            "startOfWeek()",
                            "endOfWeek()",
                        ]
                    },
                ]
            },
            {"not": {"priority__exact": "high"}},
        ]
    }


@pytest.mark.unit
def test_parse_pql_supports_enum_membership_with_a_relative_date():
    query = (
        "dueDate < today() AND priority IN (High, Urgent) "
        "AND stateGroup NOT IN (Completed, Cancelled)"
    )

    assert parse_pql(query) == {
        "and": [
            {"target_date__lt": "today()"},
            {"priority__in": ["high", "urgent"]},
            {"state_group__not_in": ["completed", "cancelled"]},
        ]
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        'password = "secret"',
        "createdAt = tomorrowish()",
        "createdAt LIKE today()",
        "createdAt = today() trailing",
        "createdAt = today(1)",
        "createdAt >= daysAgo()",
        "createdAt >= daysAgo(1, 2)",
        'createdAt = ""',
        "priority = today()",
        "dueDate >= hoursAgo(1)",
        "createdAt >= daysAgo(999999999999999999999)",
        "(" * 20 + "createdAt = today()" + ")" * 20,
        "createdAt = today() " + " " * 500,
        None,
        123,
    ],
)
def test_parse_pql_rejects_invalid_or_unsafe_queries(query):
    with pytest.raises(PQLSyntaxError):
        parse_pql(query)
