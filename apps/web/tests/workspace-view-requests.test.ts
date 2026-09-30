import { CanceledError } from "axios";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceService } from "@/services/workspace.service";
import { WorkspaceIssues } from "@/store/issue/workspace/issue.store";
import type { IWorkspaceIssuesFilter } from "@/store/issue/workspace/filter.store";
import type { IIssueRootStore } from "@/store/issue/root.store";

vi.mock("@/lib/store-context", () => ({ store: {} }));

describe("workspace layout request cancellation", () => {
  it("preserves the cancellation error in the workspace service", async () => {
    const service = new WorkspaceService();
    const cancelled = new CanceledError("superseded layout");
    vi.spyOn(service, "get").mockRejectedValueOnce(cancelled);
    await expect(service.getViewIssues("workspace", {})).rejects.toBe(cancelled);
  });

  it("settles superseded requests without clearing the replacement's loader", async () => {
    const store = new WorkspaceIssues(
      {} as IIssueRootStore,
      {
        getFilterParams: () => ({}),
      } as unknown as IWorkspaceIssuesFilter
    );
    vi.spyOn(store.workspaceService, "getViewIssues").mockRejectedValueOnce(new CanceledError("superseded layout"));
    await expect(
      store.fetchIssues("workspace", "all-issues", "init-loader", { canGroup: true, perPageCount: 50 })
    ).resolves.toBeUndefined();
    expect(store.getIssueLoader()).toBe("init-loader");
  });

  it("still reports actual request failures and clears their loader", async () => {
    const store = new WorkspaceIssues(
      {} as IIssueRootStore,
      {
        getFilterParams: () => ({}),
      } as unknown as IWorkspaceIssuesFilter
    );
    const error = new Error("request failed");
    vi.spyOn(store.workspaceService, "getViewIssues").mockRejectedValueOnce(error);
    await expect(
      store.fetchIssues("workspace", "all-issues", "init-loader", { canGroup: true, perPageCount: 50 })
    ).rejects.toBe(error);
    expect(store.getIssueLoader()).toBeUndefined();
  });
});
