# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone


class PQLSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


_TOKEN = re.compile(
    r"(?P<space>\s+)"
    r'|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r"|(?P<operator>>=|<=|!=|=|>|<)"
    r"|(?P<punctuation>[(),])"
    r"|(?P<number>\d+)"
    r"|(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)"
)

_FIELDS = {
    "createdat": "created_at",
    "duedate": "target_date",
    "priority": "priority",
    "startdate": "start_date",
    "stategroup": "state_group",
    "targetdate": "target_date",
    "updatedat": "updated_at",
}
_LOOKUPS = {
    "=": "exact",
    "<": "lt",
    "<=": "lte",
    ">": "gt",
    ">=": "gte",
}
_FUNCTIONS = {
    "daysago": ("daysAgo", True),
    "daysfromnow": ("daysFromNow", True),
    "endofday": ("endOfDay", False),
    "endofmonth": ("endOfMonth", False),
    "endofweek": ("endOfWeek", False),
    "endofyear": ("endOfYear", False),
    "hoursago": ("hoursAgo", True),
    "hoursfromnow": ("hoursFromNow", True),
    "monthsago": ("monthsAgo", True),
    "monthsfromnow": ("monthsFromNow", True),
    "now": ("now", False),
    "startofday": ("startOfDay", False),
    "startofmonth": ("startOfMonth", False),
    "startofweek": ("startOfWeek", False),
    "startofyear": ("startOfYear", False),
    "today": ("today", False),
    "weeksago": ("weeksAgo", True),
    "weeksfromnow": ("weeksFromNow", True),
}
_DATE_FIELDS = {"created_at", "start_date", "target_date", "updated_at"}
_DATETIME_FIELDS = {"created_at", "updated_at"}
_FUNCTION_ARGUMENT_LIMITS = {
    "daysAgo": 100_000,
    "daysFromNow": 100_000,
    "hoursAgo": 1_000_000,
    "hoursFromNow": 1_000_000,
    "monthsAgo": 1_200,
    "monthsFromNow": 1_200,
    "weeksAgo": 10_000,
    "weeksFromNow": 10_000,
}
_MAX_NESTING = 10
_MAX_QUERY_LENGTH = 500
_MAX_TOKENS = 200


def _tokenize(query: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while position < len(query):
        match = _TOKEN.match(query, position)
        if match is None:
            raise PQLSyntaxError(f"Unexpected character at position {position}")
        if match.lastgroup != "space":
            tokens.append(_Token(match.lastgroup or "", match.group(), position))
            if len(tokens) > _MAX_TOKENS:
                raise PQLSyntaxError("PQL query contains too many tokens")
        position = match.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.position = 0
        self.nesting = 0

    def parse(self) -> dict[str, object]:
        expression = self._parse_or()
        token = self._current()
        if token is not None:
            raise PQLSyntaxError(f"Unexpected token '{token.value}' at position {token.position}")
        return expression

    def _parse_or(self) -> dict[str, object]:
        children = [self._parse_and()]
        while self._accept_keyword("OR"):
            children.append(self._parse_and())
        return children[0] if len(children) == 1 else {"or": children}

    def _parse_and(self) -> dict[str, object]:
        children = [self._parse_not()]
        while self._accept_keyword("AND"):
            children.append(self._parse_not())
        return children[0] if len(children) == 1 else {"and": children}

    def _parse_not(self) -> dict[str, object]:
        if self._accept_keyword("NOT"):
            self._enter_nesting()
            try:
                return {"not": self._parse_not()}
            finally:
                self.nesting -= 1
        return self._parse_primary()

    def _parse_primary(self) -> dict[str, object]:
        if self._accept("punctuation", "("):
            self._enter_nesting()
            try:
                expression = self._parse_or()
                self._expect("punctuation", ")")
                return expression
            finally:
                self.nesting -= 1
        return self._parse_condition()

    def _parse_condition(self) -> dict[str, object]:
        field_token = self._expect("identifier")
        field = _FIELDS.get(field_token.value.lower())
        if field is None:
            raise PQLSyntaxError(f"Unknown field '{field_token.value}' at position {field_token.position}")

        if self._accept_keyword("BETWEEN"):
            start = self._parse_value()
            if not self._accept_keyword("AND"):
                raise PQLSyntaxError("BETWEEN requires two values separated by AND")
            end = self._parse_value()
            self._validate_value(field, start)
            self._validate_value(field, end)
            return {f"{field}__range": [start, end]}

        if self._accept_keyword("IS"):
            is_not = self._accept_keyword("NOT")
            if not self._accept_keyword("NULL"):
                raise PQLSyntaxError("IS only supports NULL or NOT NULL")
            return {f"{field}__is_empty": not is_not}

        is_not_in = False
        if self._accept_keyword("NOT"):
            if not self._accept_keyword("IN"):
                raise PQLSyntaxError("Expected IN after NOT")
            is_not_in = True
        elif self._accept_keyword("IN"):
            pass
        else:
            return self._parse_comparison(field)

        self._expect("punctuation", "(")
        values = [self._parse_value()]
        while self._accept("punctuation", ","):
            values.append(self._parse_value())
        self._expect("punctuation", ")")
        for value in values:
            self._validate_value(field, value)
        if field in ("priority", "state_group"):
            values = [value.lower() for value in values]
        lookup = "not_in" if is_not_in else "in"
        return {f"{field}__{lookup}": values}

    def _parse_comparison(self, field: str) -> dict[str, object]:
        operator_token = self._expect("operator")
        if operator_token.value == "!=":
            value = self._parse_value()
            self._validate_value(field, value)
            if field in ("priority", "state_group"):
                value = value.lower()
            return {"not": {f"{field}__exact": value}}
        lookup = _LOOKUPS.get(operator_token.value)
        if lookup is None:
            raise PQLSyntaxError(f"Unsupported operator '{operator_token.value}'")
        value = self._parse_value()
        self._validate_value(field, value)
        if field in ("priority", "state_group"):
            value = value.lower()
        return {f"{field}__{lookup}": value}

    def _parse_value(self) -> str:
        token = self._current()
        if token is None:
            raise PQLSyntaxError("Expected a value at the end of the query")
        if token.kind == "string":
            self.position += 1
            value = token.value[1:-1]
            if not value:
                raise PQLSyntaxError("PQL values must not be empty")
            return value
        if token.kind in ("number", "identifier"):
            self.position += 1
        else:
            raise PQLSyntaxError(f"Expected a value at position {token.position}")

        if token.kind != "identifier" or not self._accept("punctuation", "("):
            return token.value

        function = _FUNCTIONS.get(token.value.lower())
        if function is None:
            raise PQLSyntaxError(f"Unknown function '{token.value}' at position {token.position}")
        function_name, takes_argument = function
        argument = self._expect("number").value if takes_argument else ""
        if argument and int(argument) > _FUNCTION_ARGUMENT_LIMITS[function_name]:
            raise PQLSyntaxError("Relative date offset is too large")
        self._expect("punctuation", ")")
        return f"{function_name}({argument})"

    def _validate_value(self, field: str, value: str) -> None:
        if not any(value.startswith(f"{name}(") for name, _ in _FUNCTIONS.values()):
            return
        if field not in _DATE_FIELDS:
            raise PQLSyntaxError("Date functions can only be used with date fields")
        if value.startswith(("hoursAgo(", "hoursFromNow(")) and field not in _DATETIME_FIELDS:
            raise PQLSyntaxError("Hour functions require createdAt or updatedAt")

    def _enter_nesting(self) -> None:
        self.nesting += 1
        if self.nesting > _MAX_NESTING:
            raise PQLSyntaxError(f"PQL nesting exceeds the maximum of {_MAX_NESTING}")

    def _current(self) -> _Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def _accept(self, kind: str, value: str | None = None) -> bool:
        token = self._current()
        if token is None or token.kind != kind or (value is not None and token.value != value):
            return False
        self.position += 1
        return True

    def _accept_keyword(self, keyword: str) -> bool:
        token = self._current()
        if token is None or token.kind != "identifier" or token.value.upper() != keyword:
            return False
        self.position += 1
        return True

    def _expect(self, kind: str, value: str | None = None) -> _Token:
        token = self._current()
        if token is None or token.kind != kind or (value is not None and token.value != value):
            expected = value or kind
            position = token.position if token else "end"
            raise PQLSyntaxError(f"Expected '{expected}' at position {position}")
        self.position += 1
        return token


def parse_pql(query: str) -> dict[str, object]:
    """Parse a PQL expression into the rich-filter representation."""
    if not isinstance(query, str) or not query.strip():
        raise PQLSyntaxError("PQL query must be a non-empty string")
    if len(query) > _MAX_QUERY_LENGTH:
        raise PQLSyntaxError(f"PQL query exceeds the maximum length of {_MAX_QUERY_LENGTH}")
    return _Parser(_tokenize(query)).parse()


def resolve_relative_dates(expression: dict[str, object], reference_time=None) -> dict[str, object]:
    """Resolve PQL date functions using the request's active timezone."""
    reference_time = reference_time or timezone.now()
    try:
        today = timezone.localtime(reference_time).date()
    except (OverflowError, ValueError) as exc:
        raise PQLSyntaxError("Relative date is outside the supported range") from exc

    def shift_months(value: date, count: int) -> date:
        month_index = value.year * 12 + value.month - 1 + count
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    def resolve(node):
        if isinstance(node, dict):
            resolved = {}
            for key, value in node.items():
                relative_hours = re.fullmatch(r"hours(Ago|FromNow)\((\d+)\)", value) if isinstance(value, str) else None
                if relative_hours and key.rsplit("__", 1)[0] in ("created_at", "updated_at"):
                    direction = -1 if relative_hours.group(1) == "Ago" else 1
                    instant = reference_time + timedelta(hours=direction * int(relative_hours.group(2)))
                    resolved[f"{key}_datetime"] = instant.isoformat()
                else:
                    resolved[key] = resolve(value)
            return resolved
        if isinstance(node, list):
            return [resolve(value) for value in node]
        if isinstance(node, str):
            if node in ("now()", "today()", "startOfDay()", "endOfDay()"):
                return today.isoformat()
            relative_days = re.fullmatch(r"days(Ago|FromNow)\((\d+)\)", node)
            if relative_days:
                direction = -1 if relative_days.group(1) == "Ago" else 1
                return (today + timedelta(days=direction * int(relative_days.group(2)))).isoformat()
            relative_weeks = re.fullmatch(r"weeks(Ago|FromNow)\((\d+)\)", node)
            if relative_weeks:
                direction = -1 if relative_weeks.group(1) == "Ago" else 1
                return (today + timedelta(weeks=direction * int(relative_weeks.group(2)))).isoformat()
            relative_months = re.fullmatch(r"months(Ago|FromNow)\((\d+)\)", node)
            if relative_months:
                direction = -1 if relative_months.group(1) == "Ago" else 1
                return shift_months(today, direction * int(relative_months.group(2))).isoformat()
            if node == "startOfWeek()":
                return (today - timedelta(days=today.weekday())).isoformat()
            if node == "endOfWeek()":
                return (today + timedelta(days=6 - today.weekday())).isoformat()
            if node == "startOfMonth()":
                return today.replace(day=1).isoformat()
            if node == "endOfMonth()":
                return today.replace(day=calendar.monthrange(today.year, today.month)[1]).isoformat()
            if node == "startOfYear()":
                return today.replace(month=1, day=1).isoformat()
            if node == "endOfYear()":
                return today.replace(month=12, day=31).isoformat()
        return node

    try:
        return resolve(expression)
    except (OverflowError, ValueError) as exc:
        raise PQLSyntaxError("Relative date is outside the supported range") from exc
