/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TAgentOptions, TAgentProfile, TProjectAgent } from "@plane/types";
import { APIService } from "./api.service";

export class AgentService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(): Promise<TAgentProfile[]> {
    return (await this.get("/api/instances/agents/")).data;
  }

  async options(): Promise<TAgentOptions> {
    return (await this.get("/api/instances/agents/options/")).data;
  }

  async save(data: Partial<TAgentProfile>): Promise<TAgentProfile> {
    const { id, ...body } = data;
    return (
      id ? await this.patch(`/api/instances/agents/${id}/`, body) : await this.post("/api/instances/agents/", body)
    ).data;
  }

  async projectAgents(workspaceSlug: string, projectId: string): Promise<TProjectAgent[]> {
    return (await this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/agents/`)).data;
  }
}
