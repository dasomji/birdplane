/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { AgentService } from "@plane/services";
import type { TIssueOperations } from "./root";

const agentService = new AgentService();

export function IssueAgentSelect(props: {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  value?: string | null;
  isEditable: boolean;
  issueOperations: TIssueOperations;
}) {
  const { workspaceSlug, projectId, issueId, value, isEditable, issueOperations } = props;
  const {
    data: agents,
    error,
    isLoading,
  } = useSWR(["PROJECT_AGENTS", workspaceSlug, projectId], () => agentService.projectAgents(workspaceSlug, projectId));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string>();
  const selected = agents?.find((agent) => agent.id === value);
  const disabled = !isEditable || saving || isLoading || !!error || (!!value && !selected?.can_unassign);

  return (
    <div className="w-full">
      <select
        aria-label="AI agent"
        className="h-7.5 w-full rounded-sm bg-transparent px-2 text-body-xs-regular disabled:opacity-60"
        value={value ?? ""}
        disabled={disabled}
        title={selected?.description}
        onChange={async (event) => {
          setSaving(true);
          setSaveError(undefined);
          try {
            await issueOperations.update(workspaceSlug, projectId, issueId, {
              agent_id: event.target.value || null,
              ...(event.target.value ? { assignee_ids: [] } : {}),
            });
          } catch {
            setSaveError("Could not update agent assignment.");
          } finally {
            setSaving(false);
          }
        }}
      >
        <option value="">No agent</option>
        {value && !selected && <option value={value}>Assigned agent</option>}
        {agents
          ?.filter((agent) => agent.can_assign || agent.id === value)
          .map((agent) => (
            <option key={agent.id} value={agent.id} disabled={!agent.can_assign}>
              {agent.name}
              {!agent.is_active ? " (inactive)" : ""}
            </option>
          ))}
      </select>
      {(error || saveError) && (
        <p role="alert" className="px-2 text-body-xs-regular text-danger-primary">
          {saveError ?? "Could not load agents."}
        </p>
      )}
    </div>
  );
}
