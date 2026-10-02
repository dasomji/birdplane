import { beforeEach, describe, expect, it, vi } from "vitest";
import { EIssueFilterType } from "@plane/constants";
import type { IWorkspaceView } from "@plane/types";
import { GlobalViewStore } from "@/store/global-view.store";
import type { CoreRootStore } from "@/store/root.store";

const api = vi.hoisted(() => ({ updateView: vi.fn() }));
vi.mock("@/services/workspace.service", () => ({
  WorkspaceService: class {
    updateView = api.updateView;
  },
}));
const updateFilters = vi.fn();
let store: GlobalViewStore;
const oldView = {
  id: "saved",
  rich_filters: {},
  display_filters: { layout: "list", group_by: "project" },
} as IWorkspaceView;
beforeEach(() => {
  vi.clearAllMocks();
  store = new GlobalViewStore({ issue: { workspaceIssuesFilter: { updateFilters } } } as unknown as CoreRootStore);
  store.globalViewMap.saved = structuredClone(oldView);
});
describe("saved workspace view preferences", () => {
  it("persists and applies layout/grouping when editing a saved view", async () => {
    const display_filters = { layout: "kanban" as const, group_by: "state_detail.group" as const };
    api.updateView.mockResolvedValue({ ...oldView, display_filters });
    await store.updateGlobalView("personal", "saved", { display_filters });
    expect(api.updateView).toHaveBeenCalledWith("personal", "saved", { display_filters });
    expect(store.getViewDetailsById("saved")?.display_filters).toEqual(display_filters);
    expect(updateFilters).toHaveBeenCalledWith(
      "personal",
      undefined,
      EIssueFilterType.DISPLAY_FILTERS,
      display_filters,
      "saved"
    );
  });
  it("restores saved preferences and reports persistence failures", async () => {
    api.updateView.mockRejectedValue(new Error("Offline"));
    await expect(
      store.updateGlobalView("personal", "saved", { display_filters: { layout: "kanban" } })
    ).rejects.toThrow("Offline");
    expect(store.getViewDetailsById("saved")?.display_filters).toEqual(oldView.display_filters);
    expect(updateFilters).not.toHaveBeenCalled();
  });
});
