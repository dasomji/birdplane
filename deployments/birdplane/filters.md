# Birdplane filters

Birdplane extends Plane v1.4.2's existing rich-filter framework with `is`, `is not`, and `is empty`. Existing saved filters keep working. Required properties (project, state, created/updated timestamps) do not offer `is empty`.

- **is**: matches any selected value.
- **is not**: matches none of the selected values, including tickets with no value.
- **is empty**: no active relationship or date; priority's `none` counts as empty. No value picker is needed.
- Multiple conditions use AND. Existing date ranges remain available.
- Negated relation membership uses a subquery, so additional labels and soft-deleted assignments cannot produce false matches. Each relation condition gets an independent join.

The public project work-item endpoint accepts the same structured `filters` JSON as the web app, validated by `IssueFilterSet` and applied before pagination. PQL remains unsupported. Existing project/workspace permissions still apply.

```json
{ "and": [{ "label_id__not_in": "<label UUID>" }, { "assignee_id__is_empty": true }] }
```

The MCP keeps its existing tool count and bounded responses. `list_issues` accepts up to 20 `filters`, resolves exact names internally, and sends them to the API:

```json
{
  "project": "BIRD",
  "filters": [
    { "field": "label", "operator": "is_not", "value": ["Blog", "Internal"] },
    { "field": "assignee", "operator": "is_empty" }
  ]
}
```

Name filters require a project; UUIDs work across projects. Supported fields: state, priority, assignee, label, cycle, module, created_by, subscriber, parent, start_date, due_date, created_at, updated_at. Date comparisons require one `YYYY-MM-DD` value. Follow cursors using identical arguments. Existing scalar equality arguments remain compatible and combine with the new filters.

## Verification

- Backend: `docker compose -p birdplane-filter-tests -f deployments/birdplane/recurrence-test.yml up -d redis`, then `docker compose -p birdplane-filter-tests -f deployments/birdplane/recurrence-test.yml run --rm tests`.
- MCP: `cd apps/mcp && uv run pytest -q`.
- Frontend: `pnpm turbo run check:types --filter=web --filter=@plane/shared-state --filter=@plane/utils --filter=@plane/types`; build shared state, then `node --test packages/shared-state/filters.test.mjs`.
- Web production build: `pnpm turbo run build --filter=web`.

The source deployment override now builds both backend and web from the pinned Birdplane commit. Preserve existing Compose service names, environment, and named volumes. No database migration is introduced by these filters.
