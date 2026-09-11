/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
// services
import { APIService } from "@/services/api.service";

export type TPQLValidationResponse = {
  filters: Record<string, unknown>;
};

export class PQLService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async validate(workspaceSlug: string, query: string): Promise<TPQLValidationResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/pql/`, { query })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }
}
