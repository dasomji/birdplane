---
name: plane-project-management
description: Use Plane to establish and maintain project tracking for substantial work in a Git repository. Resolve or create the repository's Plane project, persist its workspace and project mapping in root AGENTS.md, and manage relevant issues and progress. Skip trivial edits and questions that do not benefit from durable tracking.
---

# Plane project management

Use Birdplane's MCP tools as the durable project tracker. Establish the
repository-to-Plane mapping before creating or updating issues.

## Using Birdplane

- Use `list_workspaces` to discover accessible workspaces. Pass the chosen slug
  as `workspace` on every scoped call. Omission uses the server's configured
  default, if any; selecting a workspace never changes later calls.
- Use `list_projects` to find projects, `list_issues` to search tickets,
  `get_issue` for details, and `save_issue` to create or update. Names and ticket
  identifiers resolve within the selected workspace. Use `list_metadata` for
  valid states, labels and members; comments and recurring tasks have their own tools.
- Results are bounded. Follow cursors and description offsets, retaining the
  workspace and filters. Search multiple workspaces with separate calls.
- Omitted update fields stay unchanged. Read back writes after transport failures
  before retrying, because the operation may already have succeeded.
- For work outside a repository, use the user's explicit workspace/project choice
  or a verified mapping in the host's persistent project configuration. If the host
  cannot persist configuration, explain that limitation; do not claim it was saved.
  Apply the repository tracking workflow below only when relevant to the user's task.

## Resolve the Plane project

1. Resolve the Git repository root. For a worktree, identify the repository from
   its `origin` remote or project metadata rather than a generated worktree folder
   suffix.
2. Read the root `AGENTS.md`, if present. A block delimited by
   `<!-- BEGIN PLANE PROJECT -->` and `<!-- END PLANE PROJECT -->` is authoritative.
   Use its recorded workspace slug explicitly on every workspace-scoped MCP call.
   Validate the project with `get_project(workspace=slug, project=project_id)`
   before writing Plane data; use the identifier if a project ID is not yet recorded.
   Do not rediscover or infer a different workspace when a verified mapping exists.
   If access fails or an ID differs, report the mismatch instead of silently
   falling back to the server default or another workspace.
   For a missing or legacy mapping without a workspace, call `list_workspaces`
   and follow pagination. Use an explicitly established workspace from the current
   task when available and verify it. Otherwise search candidate projects across
   accessible workspaces, passing each slug explicitly. Reuse only an unambiguous
   repository/project match. Ask the user if multiple matches remain, or if creating
   a project requires choosing among multiple workspaces. The server default alone
   is not evidence of the repository's intended workspace.
3. If no mapping exists, derive candidate names from the origin repository name,
   package metadata, and README title. Use `list_projects(workspace=slug)` to look for existing
   projects. Reuse a project only when its name or identifier is an unambiguous
   match, or its description identifies the same repository. Ask the user when
   multiple plausible projects remain; do not guess or create a duplicate.
4. If no fitting project exists, call `create_project(workspace=slug, ...)` in the
   resolved workspace. Choose a readable project
   name and a short uppercase alphanumeric identifier that starts with a letter
   and is at most 12 characters. Check both for collisions first. Put the origin
   URL and canonical repository path in the description when available. Do not
   retry a rejected creation with speculative identifiers.
5. After resolving or successfully creating the project, add or update this
   managed block in the root `AGENTS.md`, preserving every unrelated instruction:

   ```md
   <!-- BEGIN PLANE PROJECT -->

   ## Plane project

   - Workspace: Example team
   - Workspace slug: example-team
   - Workspace ID: <verified workspace UUID>
   - Name: Example
   - Identifier: EXAMPLE
   - Project ID: <verified project UUID>
   <!-- END PLANE PROJECT -->
   ```

   Create the root `AGENTS.md` if it is absent. Never record a mapping before Plane
   confirms the workspace and project exist. Upgrade legacy blocks after verification.
   Include the Plane instance URL from project links when available, so a mapping
   cannot silently be reused against a different installation.
   This block is the persistent repository configuration; do not store credentials
   or rely on remembered session state. Names and identifiers aid readability;
   use the workspace slug and project UUID for tool calls.

## Track the work

- Use Plane when the work has multiple meaningful steps, spans sessions, needs a
  durable backlog or status, or the user asks for planning or project management.
- Search the mapped project for an existing issue that represents the requested
  work before creating one. Reuse only a clear match.
- Pass the recorded `workspace` on every project, issue, metadata, comment, and
  recurring-task call, including reads and pagination. Ticket prefixes can repeat
  across workspaces. A workspace argument affects only that call; it does not
  select a workspace for later calls.
- Keep issue descriptions outcome-focused: goal, relevant constraints, acceptance
  criteria, and useful references. Do not copy the conversation or expose secrets.
- Use project metadata to select valid state names. Add comments for meaningful
  milestones, decisions, blockers, and verification results rather than routine
  narration.
- Mark work complete only after the requested outcome is implemented and verified.
  Leave a concise final comment with the result and validation evidence.

## Boundaries

- If the Plane MCP tools are unavailable, continue work that does not depend on
  Plane and report that tracking could not be established. Do not write an
  unverified mapping.
- Do not delete Plane projects or issues through this skill.
- Do not create tracking for throwaway checkouts, dependency caches, trivial
  one-line changes, or read-only questions unless the user explicitly asks.
