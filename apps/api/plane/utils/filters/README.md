# Work-item filters and relative-date PQL

Work-item endpoints accept a JSON `filters` query parameter. Saved project and
workspace views store the same expression in `rich_filters`.

```json
{
  "and": [{ "priority__in": "high,urgent" }, { "pql__exact": "createdAt >= daysAgo(7)" }]
}
```

The PQL condition is stored as text. The server parses and evaluates it on each
request, so a saved view continues to mean “the last seven days” tomorrow.
PQL conditions can be combined with Basic filters; both must match.

The public work-item list also accepts `?pql=createdAt%20%3D%20today()`.
When both `pql` and JSON `filters` are supplied, both restrictions apply.

The web editor validates queries with `POST /api/workspaces/<slug>/pql/` and a
JSON body such as `{"query": "createdAt = today()"}`. Validation requires an
active workspace membership. Its parsed response is for validation; saved views
retain the original query text.

## Writing a relative-date query

In the work-item filter row or a view's filter form, choose **PQL**, enter a query,
and apply it. Use **Save view** or **Update view** to retain it.

Examples:

```text
createdAt = today()
createdAt >= daysAgo(7)
createdAt >= hoursAgo(24)
dueDate BETWEEN startOfWeek() AND endOfWeek()
dueDate < today() AND priority IN (High, Urgent)
(createdAt = today() OR updatedAt = today()) AND NOT priority = None
```

Date fields are `startDate`, `dueDate`, `createdAt`, and `updatedAt`. Date
comparisons support `=`, `!=`, `<`, `<=`, `>`, `>=`, and inclusive `BETWEEN`.
Use `IS NULL` / `IS NOT NULL` for unset/set dates, and `AND`, `OR`, `NOT`, and
parentheses to combine conditions. PQL is based on
[Plane's documented syntax](https://docs.plane.so/core-concepts/issues/plane-query-language);
unsupported fields, functions, or clauses produce an error.

This PQL implementation supports the four date fields, `priority`, and
`stateGroup`. Priority and state-group conditions support `=`, `!=`, `IN`, and
`NOT IN`. Queries are limited to 500 characters. Other work-item properties can
be combined with the query using Basic filters.

| Calendar function                                | Meaning                                                           |
| ------------------------------------------------ | ----------------------------------------------------------------- |
| `today()`, `now()`, `startOfDay()`, `endOfDay()` | Today's calendar date                                             |
| `startOfWeek()`, `endOfWeek()`                   | Monday and Sunday of this week                                    |
| `startOfMonth()`, `endOfMonth()`                 | First and last day of this month                                  |
| `startOfYear()`, `endOfYear()`                   | First and last day of this year                                   |
| `daysAgo(n)`, `daysFromNow(n)`                   | A date before or after today                                      |
| `weeksAgo(n)`, `weeksFromNow(n)`                 | A date offset by whole weeks                                      |
| `monthsAgo(n)`, `monthsFromNow(n)`               | A date offset by calendar months, clamped to the month's last day |

`hoursAgo(n)` and `hoursFromNow(n)` are Birdplane extensions for rolling time
windows on `createdAt` and `updatedAt`, using `<`, `<=`, `>`, or `>=`. Combine
two comparisons with `AND` for an hourly range. For example,
`createdAt >= hoursAgo(24)` compares exact timestamps;
`createdAt >= daysAgo(1)` starts at yesterday's local midnight.
`now()` follows Plane's calendar-date semantics rather than this hourly behavior.

## Evaluation and scope

Calendar dates use the requesting user's configured timezone, including
`createdAt` and `updatedAt` comparisons. Calendar boundaries are not calculated
in the browser. Date expressions remain expressions when a view is saved.

PQL expands into the existing rich-filter grammar and passes through the
endpoint's filter allowlist. It only narrows the endpoint's existing queryset;
it does not grant access to another project or workspace.

Keep the raw `pql__exact` expression when saving filters. Do not replace it with
resolved dates or a cached result from a previous request.
