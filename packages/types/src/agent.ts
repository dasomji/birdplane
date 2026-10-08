/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TAgentScope = { workspace: string; all_projects: boolean; projects: string[] };
export type TAgentProfile = {
  id: string;
  name: string;
  description: string;
  owner: string;
  assigners: string[];
  scopes: TAgentScope[];
  is_active: boolean;
};
export type TProjectAgent = Pick<TAgentProfile, "id" | "name" | "description" | "is_active"> & {
  can_assign: boolean;
  can_unassign: boolean;
};
export type TAgentOptions = {
  workspaces: { id: string; name: string }[];
  projects: { id: string; name: string; workspace_id: string }[];
  members: { id: string; display_name: string; email: string }[];
};
