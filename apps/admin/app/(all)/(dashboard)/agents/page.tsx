/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { AgentService } from "@plane/services";
import type { TAgentProfile, TAgentScope } from "@plane/types";
import { PageWrapper } from "@/components/common/page-wrapper";
import { useUser } from "@/hooks/store";

const agentService = new AgentService();
type Draft = Pick<TAgentProfile, "name" | "description" | "assigners" | "scopes" | "is_active"> & { id?: string };
const newDraft = (): Draft => ({ name: "", description: "", assigners: [], scopes: [], is_active: true });

export default observer(function AgentsPage() {
  const { currentUser } = useUser();
  const { data: agents, error: loadError, mutate } = useSWR("INSTANCE_AGENTS", () => agentService.list());
  const { data: options, error: optionsError } = useSWR("INSTANCE_AGENT_OPTIONS", () => agentService.options());
  const [draft, setDraft] = useState<Draft>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const setScope = (workspaceId: string, scope?: TAgentScope) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            scopes: [...current.scopes.filter((item) => item.workspace !== workspaceId), ...(scope ? [scope] : [])],
          }
        : current
    );
  const scopesByWorkspace = new Map(draft?.scopes.map((scope) => [scope.workspace, scope]));
  const selectedAssigners = new Set(draft?.assigners);
  const inputClass = "w-full rounded border border-subtle bg-transparent p-2";

  return (
    <PageWrapper
      header={{
        title: "AI agents",
        description: "Create agent profiles and choose where and by whom they can be assigned.",
      }}
    >
      {(loadError || optionsError) && <p role="alert">Could not load agent settings.</p>}
      {!agents && !loadError && <p>Loading agents…</p>}
      <div className="space-y-4">
        <Button
          disabled={!options || saving}
          onClick={() => {
            setDraft(newDraft());
            setError(undefined);
          }}
        >
          Create agent
        </Button>
        {agents?.length === 0 && <p>No agents yet.</p>}
        {agents?.map((agent) => (
          <div key={agent.id} className="flex items-center justify-between gap-4 rounded border border-subtle p-4">
            <div>
              <h3 className="text-body-sm-medium">
                {agent.name}
                {!agent.is_active && " (inactive)"}
              </h3>
              <p className="text-body-sm-regular text-secondary">{agent.description}</p>
              <p className="text-body-xs-regular text-tertiary">
                {agent.scopes.length} workspaces ·{" "}
                {agent.assigners.length
                  ? `Creator and ${agent.assigners.length} colleagues can assign`
                  : "Only the creator can assign"}
              </p>
            </div>
            {agent.owner === currentUser?.id && (
              <Button
                disabled={saving}
                variant="secondary"
                onClick={() => {
                  setDraft({ ...agent });
                  setError(undefined);
                }}
              >
                Edit
              </Button>
            )}
          </div>
        ))}
        {draft && options && (
          <form
            className="space-y-5 rounded border border-subtle p-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setSaving(true);
              setError(undefined);
              try {
                await agentService.save(draft);
                await mutate();
                setDraft(undefined);
              } catch {
                setError("Could not save agent profile. Check the selections and try again.");
              } finally {
                setSaving(false);
              }
            }}
          >
            <fieldset disabled={saving} className="space-y-5">
              <legend className="mb-3 text-body-sm-medium">{draft.id ? "Edit agent" : "Create agent"}</legend>
              <label className="block space-y-1">
                Name
                <input
                  className={inputClass}
                  required
                  maxLength={255}
                  value={draft.name}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                />
              </label>
              <label className="block space-y-1">
                Description
                <textarea
                  className={inputClass}
                  rows={3}
                  value={draft.description}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                />
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.is_active}
                  onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })}
                />
                Active
              </label>
              <fieldset className="space-y-3">
                <legend className="text-body-sm-medium">Workspaces and projects</legend>
                <p className="text-body-xs-regular text-secondary">
                  Enable a workspace, then choose all projects or specific projects.
                </p>
                {options.workspaces.map((workspace) => {
                  const scope = scopesByWorkspace.get(workspace.id);
                  const selectedProjects = new Set(scope?.projects);
                  return (
                    <div key={workspace.id} className="space-y-2 rounded border border-subtle p-3">
                      <label className="flex gap-2">
                        <input
                          type="checkbox"
                          checked={!!scope}
                          onChange={(event) =>
                            setScope(
                              workspace.id,
                              event.target.checked
                                ? { workspace: workspace.id, all_projects: true, projects: [] }
                                : undefined
                            )
                          }
                        />
                        {workspace.name}
                      </label>
                      {scope && (
                        <div className="ml-6 space-y-2">
                          <label className="flex gap-2">
                            <input
                              type="checkbox"
                              checked={scope.all_projects}
                              onChange={(event) =>
                                setScope(workspace.id, { ...scope, all_projects: event.target.checked, projects: [] })
                              }
                            />
                            All projects, including future projects
                          </label>
                          {!scope.all_projects &&
                            options.projects
                              .filter((project) => project.workspace_id === workspace.id)
                              .map((project) => (
                                <label key={project.id} className="flex gap-2">
                                  <input
                                    type="checkbox"
                                    checked={selectedProjects.has(project.id)}
                                    onChange={(event) =>
                                      setScope(workspace.id, {
                                        ...scope,
                                        projects: event.target.checked
                                          ? [...scope.projects, project.id]
                                          : scope.projects.filter((id) => id !== project.id),
                                      })
                                    }
                                  />
                                  {project.name}
                                </label>
                              ))}
                          {!scope.all_projects && !scope.projects.length && (
                            <p className="text-body-xs-regular text-secondary">
                              Select projects to allow assignment in this workspace.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-body-sm-medium">Who can assign</legend>
                <p className="text-body-xs-regular text-secondary">
                  You can always assign your agent. Select colleagues to grant them permission too.
                </p>
                <div className="max-h-60 space-y-2 overflow-y-auto">
                  {options.members
                    .filter((member) => member.id !== currentUser?.id)
                    .map((member) => (
                      <label key={member.id} className="flex gap-2">
                        <input
                          type="checkbox"
                          checked={selectedAssigners.has(member.id)}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              assigners: event.target.checked
                                ? [...draft.assigners, member.id]
                                : draft.assigners.filter((id) => id !== member.id),
                            })
                          }
                        />
                        {member.display_name || member.email}
                      </label>
                    ))}
                </div>
              </fieldset>
              {error && <p role="alert">{error}</p>}
              <div className="flex gap-2">
                <Button type="submit" loading={saving}>
                  Save agent
                </Button>
                <Button type="button" variant="secondary" onClick={() => setDraft(undefined)}>
                  Cancel
                </Button>
              </div>
            </fieldset>
          </form>
        )}
      </div>
    </PageWrapper>
  );
});
