"""Plane API boundary, identity resolution, and bounded agent-facing projections."""

import base64
import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import quote
from uuid import UUID

import httpx
from markdown_it import MarkdownIt


class PlaneError(Exception):
    def __init__(self, code, message, **details):
        self.payload = {"error": code, "message": message, **details}
        super().__init__(message)


def uuid(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def ident(value):
    if isinstance(value, dict):
        return value.get("id")
    return value


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li", "h1", "h2", "h3", "pre", "tr"}:
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")


def plain(html):
    parser = PlainText()
    parser.feed(html or "")
    return "".join(parser.parts).strip()


def body_chunk(text, offset=0, limit=4000):
    result = {"text": text[offset : offset + limit], "length": len(text)}
    if offset + limit < len(text):
        result["next_offset"] = offset + limit
    return result


def markdown(text):
    return MarkdownIt("commonmark", {"html": False}).render(text)


def select(row, keys):
    return {k: row[k] for k in keys if row.get(k) is not None}


class Plane:
    def __init__(self, client: httpx.AsyncClient, base_url: str, workspace: str):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.workspace = workspace
        self.root = f"{self.base_url}/api/v1/workspaces/{quote(workspace, safe='')}/"
        # Per-tool-call cache only: no cross-user or stale write resolution.
        self.catalogs = {}

    async def request(self, method, path, **kwargs):
        try:
            response = await self.client.request(
                method, self.root + path.strip("/") + "/", **kwargs
            )
        except httpx.RequestError:
            raise PlaneError(
                "transport_error",
                "Plane request failed. For writes, read back before retrying; the outcome may be unknown.",
            ) from None
        if response.status_code >= 400:
            # Never leak arbitrary upstream bodies, stack traces or credentials.
            hints = {
                400: "Plane rejected the fields or filter.",
                401: "Plane API credential is invalid.",
                403: "Plane denied access.",
                404: "Resource or feature is unavailable.",
                409: "The change conflicts with current data.",
                429: "Plane rate limit reached; retry later.",
            }
            details = {"status": response.status_code}
            if response.status_code == 429:
                retry = response.headers.get("retry-after", "")
                if retry.isdigit():
                    details["retry_after_seconds"] = int(retry)
            raise PlaneError(
                "plane_api_error",
                hints.get(
                    response.status_code,
                    "Plane request failed; read back writes before retrying.",
                ),
                **details,
            )
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def catalog(self, path):
        if path in self.catalogs:
            return self.catalogs[path]
        rows, cursor, seen = [], None, set()
        for _ in range(20):
            data = await self.request(
                "GET",
                path,
                params={"per_page": 100, **({"cursor": cursor} if cursor else {})},
            )
            if isinstance(data, list):
                rows.extend(data)
                break
            rows.extend(data.get("results", []))
            if not data.get("next_page_results"):
                break
            cursor = data.get("next_cursor")
            if not cursor or cursor in seen:
                raise PlaneError(
                    "invalid_pagination", "Plane returned an unusable cursor."
                )
            seen.add(cursor)
        else:
            raise PlaneError(
                "resolution_limit", "Name resolution exceeded 2000 entries. Use a UUID."
            )
        self.catalogs[path] = rows
        return rows

    @staticmethod
    def resolve(rows, value, kind):
        key = value.casefold()
        matches = []
        for row in rows:
            names = [
                row.get(k)
                for k in ("id", "name", "identifier", "display_name", "email")
            ]
            names.append(
                " ".join(
                    filter(None, [row.get("first_name"), row.get("last_name")])
                ).strip()
            )
            if any(str(n).casefold() == key for n in names if n):
                matches.append(row)
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise PlaneError(
                "ambiguous_name",
                f"Multiple {kind} entries match. Use a UUID.",
                candidates=[
                    select(r, ["id", "name", "identifier", "display_name"])
                    for r in matches[:10]
                ],
            )
        raise PlaneError(
            "not_found",
            f"No exact {kind} match. Use list_projects or list_metadata to find a valid value.",
        )

    async def project(self, value):
        if uuid(value):
            return await self.request("GET", f"projects/{uuid(value)}")
        return self.resolve(await self.catalog("projects-lite"), value, "project")

    async def metadata(self, pid, kind):
        endpoint = {"members": "project-members-lite", "types": "work-item-types"}.get(
            kind, kind
        )
        return await self.catalog(f"projects/{pid}/{endpoint}")

    async def reference(self, pid, kind, value):
        if uuid(value):
            return uuid(value)
        if kind == "members" and value == "me":
            response = await self.client.get(self.base_url + "/api/v1/users/me/")
            if response.status_code != 200:
                raise PlaneError(
                    "identity_unavailable",
                    "Cannot resolve me; use your member UUID or email.",
                )
            return response.json()["id"]
        return self.resolve(await self.metadata(pid, kind), value, kind)["id"]

    async def issue(self, value, project=None):
        params = {"expand": "state,project,assignees,labels"}
        if uuid(value):
            if not project:
                raise PlaneError(
                    "project_required",
                    "A ticket UUID requires project; identifiers such as BIRD-1 do not.",
                )
            pid = (await self.project(project))["id"]
            row = await self.request(
                "GET", f"projects/{pid}/work-items/{uuid(value)}", params=params
            )
        else:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*-[0-9]+", value):
                raise PlaneError(
                    "invalid_identifier",
                    "Use a ticket identifier such as BIRD-1 or UUID plus project.",
                )
            row = await self.request(
                "GET", f"work-items/{quote(value.upper(), safe='')}", params=params
            )
            if (
                project
                and ident(row.get("project")) != (await self.project(project))["id"]
            ):
                raise PlaneError(
                    "project_mismatch",
                    "Ticket belongs to a different project; no change was made.",
                )
        return row

    def summary(self, row, fields=None, description_offset=0, description_limit=4000):
        project = row.get("project")
        pid = ident(project)
        prefix = project.get("identifier") if isinstance(project, dict) else None
        prefix = prefix or row.get("project_identifier")
        result = {"id": row["id"]}
        if prefix and row.get("sequence_id") is not None:
            result["identifier"] = f"{prefix}-{row['sequence_id']}"
        if pid:
            result["url"] = (
                f"{self.base_url}/{quote(self.workspace, safe='')}/projects/{pid}/work-items/{row['id']}"
            )
        fields = fields or ["title", "state", "priority", "project"]
        for key in fields:
            source = {
                "title": "name",
                "due_date": "target_date",
                "description": "description_html",
            }.get(key, key)
            value = row.get(source)
            if key == "description":
                result[key] = body_chunk(
                    plain(value) if value else row.get("description_stripped", ""),
                    description_offset,
                    description_limit,
                )
            elif isinstance(value, dict):
                result[key] = select(
                    value, ["id", "name", "identifier", "group", "display_name"]
                )
            elif isinstance(value, list):
                result[key] = [
                    select(v, ["id", "name", "display_name"])
                    if isinstance(v, dict)
                    else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def page(rows, args, scope):
        query = args.get("query", "").casefold()
        if query:
            rows = [
                r
                for r in rows
                if query
                in " ".join(
                    str(r.get(k, ""))
                    for k in ["name", "identifier", "display_name", "email"]
                ).casefold()
            ]
        fingerprint = hashlib.sha256((scope + query).encode()).hexdigest()[:10]
        offset = 0
        if args.get("cursor"):
            match = re.fullmatch(r"local:([a-f0-9]{10}):(\d+)", args["cursor"])
            if not match or match[1] != fingerprint:
                raise PlaneError(
                    "invalid_cursor", "Cursor does not match this list/query."
                )
            offset = int(match[2])
        limit = args.get("limit", 10)
        return {
            "results": rows[offset : offset + limit],
            "next_cursor": f"local:{fingerprint}:{offset + limit}"
            if offset + limit < len(rows)
            else None,
        }

    async def dispatch(self, name, args):
        if name == "create_project":
            body = {
                **args,
                "name": args["name"].strip(),
                "identifier": args["identifier"].upper(),
            }
            saved = await self.request("POST", "projects", json=body)
            self.catalogs.pop("projects-lite", None)
            return {
                **select(saved, ["id", "name", "identifier", "timezone"]),
                "action": "created",
            }
        if name == "create_label":
            pid = (await self.project(args["project"]))["id"]
            body = {k: v for k, v in args.items() if k != "project"}
            body["name"] = body["name"].strip()
            saved = await self.request("POST", f"projects/{pid}/labels", json=body)
            self.catalogs.pop(f"projects/{pid}/labels", None)
            return {
                **select(saved, ["id", "name", "color"]),
                "project": pid,
                "action": "created",
            }

        if name in (
            "list_recurring_tasks",
            "save_recurring_task",
            "delete_recurring_task",
        ):
            pid = (await self.project(args["project"]))["id"]
            path = f"projects/{pid}/recurring-tasks"
            if args.get("id"):
                path += f"/{args['id']}"
            if name == "list_recurring_tasks":
                return await self.request(
                    "GET", path, params={"offset": args.get("offset", 0)}
                )
            if name == "delete_recurring_task":
                await self.request("DELETE", path)
                return {"id": args["id"], "action": "deleted"}
            body = {k: v for k, v in args.items() if k not in ("id", "project")}
            if "template_issue" in body:
                body["template_issue"] = (
                    await self.issue(body["template_issue"], pid)
                )["id"]
            return await self.request(
                "PATCH" if args.get("id") else "POST", path, json=body
            )

        if name == "list_projects":
            rows = [
                select(r, ["id", "name", "identifier"])
                for r in await self.catalog("projects-lite")
            ]
            return self.page(rows, args, "projects")
        if name == "get_project":
            p = await self.project(args["project"])
            p = await self.request("GET", f"projects/{p['id']}")
            result = select(
                p,
                [
                    "id",
                    "name",
                    "identifier",
                    "project_lead",
                    "default_assignee",
                    "default_state",
                    "timezone",
                    "archived_at",
                ],
            )
            result["description"] = body_chunk(
                p.get("description") or plain(p.get("description_html")),
                offset=args.get("description_offset", 0),
                limit=4000,
            )
            return result
        if name == "list_metadata":
            pid = (await self.project(args["project"]))["id"]
            rows = [
                select(
                    r,
                    [
                        "id",
                        "name",
                        "display_name",
                        "color",
                        "email",
                        "group",
                        "is_default",
                        "start_date",
                        "end_date",
                    ],
                )
                for r in await self.metadata(pid, args["kind"])
            ]
            return self.page(rows, args, pid + args["kind"])
        if name == "list_issues":
            return await self.list_issues(args)
        if name == "save_issue":
            return await self.save_issue(args)
        row = await self.issue(args.get("issue", args.get("id")), args.get("project"))
        pid = ident(row["project"])
        path = f"projects/{pid}/work-items/{row['id']}"
        if name == "get_issue":
            return self.summary(
                row,
                args.get("fields")
                or [
                    "title",
                    "state",
                    "priority",
                    "project",
                    "assignees",
                    "labels",
                    "parent",
                    "start_date",
                    "due_date",
                    "description",
                    "updated_at",
                ],
                args.get("description_offset", 0),
                args.get("description_limit", 4000),
            )
        if name == "delete_issue":
            await self.request("DELETE", path)
            return {"id": row["id"], "deleted": True}
        if name == "list_comments":
            data = await self.request(
                "GET",
                path + "/comments",
                params={
                    "per_page": args.get("limit", 10),
                    **({"cursor": args["cursor"]} if args.get("cursor") else {}),
                },
            )
            return {
                "results": [
                    {
                        **select(r, ["id", "actor", "created_at", "updated_at"]),
                        "body": body_chunk(plain(r.get("comment_html")), limit=1000),
                    }
                    for r in data.get("results", [])
                ],
                "next_cursor": data.get("next_cursor")
                if data.get("next_page_results")
                else None,
            }
        if name == "get_comment":
            r = await self.request("GET", path + "/comments/" + args["id"])
            return {
                "id": r["id"],
                "body": body_chunk(
                    plain(r.get("comment_html")),
                    args.get("offset", 0),
                    args.get("limit", 4000),
                ),
            }
        if name == "save_comment":
            cid = args.get("id")
            r = await self.request(
                "PATCH" if cid else "POST",
                path + "/comments" + ("/" + cid if cid else ""),
                json={"comment_html": markdown(args["body"])},
            )
            return {
                "id": r["id"],
                "issue": row["id"],
                "action": "updated" if cid else "created",
            }
        raise PlaneError("unknown_tool", "Unknown tool.")

    async def issue_filters(self, conditions, pid):
        """Translate bounded agent-friendly conditions to Birdplane's shared API filters."""
        references = {
            "state": ("state_id", "states"),
            "assignee": ("assignee_id", "members"),
            "label": ("label_id", "labels"),
            "cycle": ("cycle_id", "cycles"),
            "module": ("module_id", "modules"),
            "created_by": ("created_by_id", "members"),
            "subscriber": ("subscriber_id", "members"),
        }
        dates = {"start_date", "due_date", "created_at", "updated_at"}
        result = []
        for condition in conditions:
            field, operator = condition["field"], condition["operator"]
            key = references.get(
                field,
                (
                    {"due_date": "target_date", "parent": "parent_id"}.get(
                        field, field
                    ),
                    None,
                ),
            )[0]
            if operator == "is_empty":
                if "value" in condition or field in {
                    "state",
                    "created_at",
                    "updated_at",
                }:
                    raise PlaneError(
                        "invalid_filter",
                        "is_empty takes no value and requires an optional field.",
                    )
                result.append({f"{key}__is_empty": True})
                continue
            value = condition.get("value")
            values = value if isinstance(value, list) else [value]
            if not values or any(
                not isinstance(v, str) or not v.strip() for v in values
            ):
                raise PlaneError(
                    "invalid_filter",
                    "is and is_not require a nonempty value or list of values.",
                )
            if field in dates:
                try:
                    if len(values) != 1 or not re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}", values[0]
                    ):
                        raise ValueError()
                    date.fromisoformat(values[0])
                except ValueError:
                    raise PlaneError(
                        "invalid_filter", "Date filters require one YYYY-MM-DD value."
                    ) from None
                lookup = "exact" if operator == "is" else "not_exact"
            else:
                lookup = "in" if operator == "is" else "not_in"
                if field in references:
                    kind = references[field][1]
                    if not pid and any(
                        not uuid(v) and not (kind == "members" and v == "me")
                        for v in values
                    ):
                        raise PlaneError(
                            "project_required",
                            "Name filters require project; UUIDs work workspace-wide.",
                        )
                    values = [await self.reference(pid, kind, v) for v in values]
                elif field == "parent":
                    values = [(await self.issue(v, pid))["id"] for v in values]
                elif field == "priority" and any(
                    v not in {"urgent", "high", "medium", "low", "none"} for v in values
                ):
                    raise PlaneError("invalid_filter", "Unknown priority value.")
            result.append({f"{key}__{lookup}": ",".join(values)})
        return {"and": result} if result else None

    async def list_issues(self, args):
        pid = (
            (await self.project(args["project"]))["id"] if args.get("project") else None
        )
        structured_filters = await self.issue_filters(args.get("filters", []), pid)
        resolved = {}
        for field, kind in [
            ("state", "states"),
            ("assignee", "members"),
            ("label", "labels"),
        ]:
            if field not in args:
                continue
            value = args[field]
            if (
                not pid
                and not uuid(value)
                and not (field == "assignee" and value == "me")
            ):
                raise PlaneError(
                    "project_required",
                    f"A {field} name filter requires project; a UUID works workspace-wide.",
                )
            resolved[field] = await self.reference(pid, kind, value)
        if args.get("parent"):
            parent = await self.issue(args["parent"], args.get("project"))
            resolved["parent"] = parent["id"]
            pid = pid or ident(parent["project"])
        projects = (
            [pid] if pid else [r["id"] for r in await self.catalog("projects-lite")]
        )
        if not projects:
            return {"results": [], "next_cursor": None}
        fields = args.get("fields") or ["title", "state", "priority", "project"]
        sources = {
            "id",
            "sequence_id",
            "project",
            "name",
            "state",
            "assignees",
            "labels",
            "parent",
            "priority",
        }
        sources.update(
            {
                "title": "name",
                "due_date": "target_date",
                "description": "description_html",
            }.get(k, k)
            for k in fields
        )
        # Structured operators run in Birdplane before pagination. Legacy scalar
        # filters still scan at most 500 sparse rows; no workspace dump reaches the LLM.
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "args": {k: v for k, v in args.items() if k != "cursor"},
                    "projects": projects,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        cursor, skip, project_index = None, 0, 0
        if args.get("cursor"):
            try:
                value = json.loads(base64.urlsafe_b64decode(args["cursor"]))
                if (
                    value["f"] != fingerprint
                    or not isinstance(value["s"], int)
                    or not 0 <= value["s"] <= 100
                ):
                    raise ValueError()
                cursor, skip = value["c"], value["s"]
                project_index = value["p"]
                if not isinstance(project_index, int) or not 0 <= project_index < len(
                    projects
                ):
                    raise ValueError()
                if cursor is not None and not isinstance(cursor, str):
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise PlaneError(
                    "invalid_cursor",
                    "Keep the same filters, fields and limit when following a cursor.",
                ) from None

        def encode(c, s, p=None):
            return base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "c": c,
                        "s": s,
                        "p": project_index if p is None else p,
                        "f": fingerprint,
                    },
                    separators=(",", ":"),
                ).encode()
            ).decode()

        def matches(row):
            if args.get("query", "").casefold() not in row.get("name", "").casefold():
                return False
            if args.get("priority") and row.get("priority") != args["priority"]:
                return False
            for field, value in resolved.items():
                if field in {"assignee", "label"}:
                    key = "assignees" if field == "assignee" else "labels"
                    if value not in [ident(v) for v in row.get(key, [])]:
                        return False
                elif ident(row.get(field)) != value:
                    return False
            return True

        results = []
        for _ in range(5):
            params = {
                "per_page": 100,
                "order_by": "-created_at",
                "fields": ",".join(sorted(sources)),
                "expand": "state,project,assignees,labels",
            }
            if cursor:
                params["cursor"] = cursor
            if structured_filters:
                params["filters"] = json.dumps(
                    structured_filters, separators=(",", ":")
                )
            data = await self.request(
                "GET", f"projects/{projects[project_index]}/work-items", params=params
            )
            rows = data.get("results", [])
            for index, row in enumerate(rows[skip:], start=skip):
                if matches(row):
                    results.append(self.summary(row, fields, description_limit=1000))
                if len(results) == args.get("limit", 10):
                    next_cursor = (
                        encode(cursor, index + 1)
                        if index + 1 < len(rows)
                        else (
                            encode(data["next_cursor"], 0)
                            if data.get("next_page_results")
                            else (
                                encode(None, 0, project_index + 1)
                                if project_index + 1 < len(projects)
                                else None
                            )
                        )
                    )
                    return {"results": results, "next_cursor": next_cursor}
            if not data.get("next_page_results"):
                if project_index + 1 == len(projects):
                    return {"results": results, "next_cursor": None}
                project_index += 1
                cursor, skip = None, 0
                continue
            next_page = data.get("next_cursor")
            if not next_page or next_page == cursor:
                raise PlaneError(
                    "invalid_pagination", "Plane returned an unusable cursor."
                )
            cursor, skip = next_page, 0
        return {
            "results": results,
            "next_cursor": encode(cursor, 0),
            "scan_limited": True,
        }

    async def save_issue(self, args):
        updating = "id" in args
        if not updating and (not args.get("project") or not args.get("title")):
            raise PlaneError(
                "required_fields", "Creating a ticket requires project and title."
            )
        row = await self.issue(args["id"], args.get("project")) if updating else None
        pid = (
            ident(row["project"])
            if row
            else (await self.project(args["project"]))["id"]
        )
        body = {}
        for key, target in [
            ("title", "name"),
            ("priority", "priority"),
            ("start_date", "start_date"),
            ("due_date", "target_date"),
        ]:
            if key in args:
                body[target] = args[key]
        if "description" in args:
            body["description_html"] = markdown(args["description"])
        if "state" in args:
            body["state"] = await self.reference(pid, "states", args["state"])
        if "parent" in args:
            body["parent"] = (
                (await self.issue(args["parent"], pid))["id"]
                if args["parent"]
                else None
            )
        for field, kind in [("assignees", "members"), ("labels", "labels")]:
            if field in args:
                body[field] = [await self.reference(pid, kind, v) for v in args[field]]
        if "labels" in args and ("add_labels" in args or "remove_labels" in args):
            raise PlaneError(
                "conflicting_fields",
                "Use labels replacement or add_labels/remove_labels, not both.",
            )
        if "add_labels" in args or "remove_labels" in args:
            current = [ident(v) for v in row.get("labels", [])] if row else []
            remove = [
                await self.reference(pid, "labels", v)
                for v in args.get("remove_labels", [])
            ]
            add = [
                await self.reference(pid, "labels", v)
                for v in args.get("add_labels", [])
            ]
            body["labels"] = list(
                dict.fromkeys([v for v in current if v not in remove] + add)
            )
        if not body:
            raise PlaneError("empty_update", "Supply at least one field to change.")
        path = f"projects/{pid}/work-items" + (f"/{row['id']}" if row else "")
        saved = await self.request("PATCH" if updating else "POST", path, json=body)
        # Writes return a receipt instead of the entire ticket/description.
        receipt = {
            **select(
                saved, ["id", "sequence_id", "name", "priority", "state", "updated_at"]
            ),
            "project": pid,
            "action": "updated" if updating else "created",
            "changed": sorted(body),
        }
        project = (
            row.get("project")
            if row
            else self.resolve(await self.catalog("projects-lite"), pid, "project")
        )
        if (
            isinstance(project, dict)
            and project.get("identifier")
            and saved.get("sequence_id") is not None
        ):
            receipt["identifier"] = f"{project['identifier']}-{saved['sequence_id']}"
        return receipt
