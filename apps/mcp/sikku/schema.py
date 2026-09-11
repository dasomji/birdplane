"""Explicit small schemas: no repeated server instructions or nullable defaults."""

from mcp.types import Tool, ToolAnnotations


def string(description=None, **extra):
    return {
        "type": "string",
        **({"description": description} if description else {}),
        **extra,
    }


PROJECT = string("Project UUID, exact name or prefix (e.g. BIRD).")
ISSUE = string("Ticket identifier (BIRD-1) or UUID; UUID requires project.")
PAGE = {
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    "cursor": string(),
}
PRIORITY = string(enum=["urgent", "high", "medium", "low", "none"])
NAMES = {"type": "array", "items": string(), "maxItems": 50, "uniqueItems": True}
FIELDS = {
    "type": "array",
    "items": string(
        enum=[
            "title",
            "state",
            "priority",
            "project",
            "assignees",
            "labels",
            "parent",
            "start_date",
            "due_date",
            "created_at",
            "updated_at",
            "description",
        ]
    ),
    "maxItems": 13,
    "uniqueItems": True,
}


def tool(name, description, properties, required=(), write=False, destructive=False):
    return Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties,
            "required": list(required),
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(
            readOnlyHint=not write,
            destructiveHint=destructive,
            idempotentHint=not write,
            openWorldHint=True,
        ),
    )


TOOLS = [
    tool(
        "create_project",
        "Create a project in the configured workspace. Identifier is a unique ticket prefix (e.g. APP), normalized to uppercase. Description is plain text. Returns a compact receipt.",
        {
            "name": string(minLength=1, maxLength=255, pattern=r"\S"),
            "identifier": string(
                minLength=1, maxLength=12, pattern="^[A-Za-z][A-Za-z0-9]*$"
            ),
            "description": string(maxLength=100000),
            "timezone": string(),
        },
        ["name", "identifier"],
        write=True,
    ),
    tool(
        "create_label",
        "Create a label in a project. Name must be unique within that project. Optional color is #RRGGBB. Use list_metadata(kind=labels) to find labels and save_issue to assign them. Returns a compact receipt.",
        {
            "project": PROJECT,
            "name": string(minLength=1, maxLength=255, pattern=r"\S"),
            "color": string(pattern="^#[0-9A-Fa-f]{6}$"),
            "description": string(maxLength=100000),
        },
        ["project", "name"],
        write=True,
    ),
    tool(
        "list_recurring_tasks",
        "List saved recurring schedules (20 per page), or read one by id. Templates and descriptions excluded.",
        {
            "project": PROJECT,
            "id": string(format="uuid"),
            "offset": {"type": "integer", "minimum": 0},
        },
        ["project"],
    ),
    tool(
        "save_recurring_task",
        "Create from a template ticket (template_issue, frequency, starts_at required), or edit by id. Snapshot copies title/body/priority/labels/assignees; dates shift from each run. starts_at is a future ISO timestamp with offset; timezone is IANA. Daily/weekly/monthly/yearly wall time. Missed runs coalesce to latest. Pause/resume with status; ended is final. Timing edits require a future starts_at. Omitted fields unchanged.",
        {
            "project": PROJECT,
            "id": string(format="uuid"),
            "template_issue": ISSUE,
            "frequency": string(enum=["daily", "weekly", "monthly", "yearly"]),
            "interval": {"type": "integer", "minimum": 1, "maximum": 365},
            "timezone": string(),
            "starts_at": string(format="date-time"),
            "ends_at": {"type": ["string", "null"], "format": "date-time"},
            "status": string(enum=["active", "paused", "ended"]),
        },
        ["project"],
        write=True,
    ),
    tool(
        "delete_recurring_task",
        "Delete a recurring schedule. Already generated tickets remain.",
        {"project": PROJECT, "id": string(format="uuid")},
        ["project", "id"],
        write=True,
        destructive=True,
    ),
    tool(
        "list_projects",
        "Find projects. Compact results; query matches name or prefix.",
        {"query": string(), **PAGE},
    ),
    tool(
        "get_project",
        "Read a project's description and configuration.",
        {"project": PROJECT, "description_offset": {"type": "integer", "minimum": 0}},
        ["project"],
    ),
    tool(
        "list_issues",
        "Search tickets; descriptions excluded by default. Names resolve internally. State/label/assignee names require project. Follow next_cursor with the same filters.",
        {
            "project": PROJECT,
            "query": string("Title contains this text."),
            "state": string("State name or UUID."),
            "priority": PRIORITY,
            "assignee": string("Name, email, UUID or me."),
            "label": string("Label name or UUID."),
            "parent": ISSUE,
            "fields": FIELDS,
            **PAGE,
        },
    ),
    tool(
        "get_issue",
        "Read one ticket. Description is paged; use description_offset for the next chunk. Comments are separate.",
        {
            "id": ISSUE,
            "project": PROJECT,
            "fields": FIELDS,
            "description_offset": {"type": "integer", "minimum": 0},
            "description_limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12000,
                "default": 4000,
            },
        },
        ["id"],
    ),
    tool(
        "save_issue",
        "Create (project+title required) or update (id required) a ticket. Omitted fields stay unchanged. Description accepts Markdown. Names resolve internally. Clear lists with []; clear parent/dates with null. Returns a compact receipt.",
        {
            "id": ISSUE,
            "project": PROJECT,
            "title": string(minLength=1, maxLength=255),
            "description": string(maxLength=100000),
            "state": string(),
            "priority": PRIORITY,
            "assignees": NAMES,
            "labels": NAMES,
            "add_labels": NAMES,
            "remove_labels": NAMES,
            "parent": {"type": ["string", "null"]},
            "start_date": {"type": ["string", "null"], "format": "date"},
            "due_date": {"type": ["string", "null"], "format": "date"},
        },
        write=True,
    ),
    tool(
        "delete_issue",
        "Permanently delete a ticket and its comments.",
        {"id": ISSUE, "project": PROJECT},
        ["id"],
        write=True,
        destructive=True,
    ),
    tool(
        "list_metadata",
        "List a project's states, labels, members, cycles, modules or types. Use when choosing valid values; ticket tools already resolve names.",
        {
            "project": PROJECT,
            "kind": string(
                enum=["states", "labels", "members", "cycles", "modules", "types"]
            ),
            "query": string(),
            **PAGE,
        },
        ["project", "kind"],
    ),
    tool(
        "list_comments",
        "Read a page of ticket comments. Long bodies are truncated explicitly; get_comment reads chunks.",
        {"issue": ISSUE, "project": PROJECT, **PAGE},
        ["issue"],
    ),
    tool(
        "get_comment",
        "Read a comment body in chunks.",
        {
            "issue": ISSUE,
            "project": PROJECT,
            "id": string(format="uuid"),
            "offset": {"type": "integer", "minimum": 0},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12000,
                "default": 4000,
            },
        },
        ["issue", "id"],
    ),
    tool(
        "save_comment",
        "Create or update (id supplied) a ticket comment. Body accepts Markdown. Returns a receipt.",
        {
            "issue": ISSUE,
            "project": PROJECT,
            "id": string(format="uuid"),
            "body": string(minLength=1, maxLength=100000),
        },
        ["issue", "body"],
        write=True,
    ),
]
BY_NAME = {t.name: t for t in TOOLS}
