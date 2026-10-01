import { beforeEach, describe, expect, it, vi } from "vitest";
import { EIssueFilterType, ISSUE_DISPLAY_FILTERS_BY_PAGE } from "@plane/constants";
import { EIssueLayoutTypes } from "@plane/types";
import type { IIssueDisplayFilterOptions } from "@plane/types";
import { WorkspaceIssuesFilter } from "@/store/issue/workspace/filter.store";
import type { IIssueRootStore } from "@/store/issue/root.store";
import { getWorkspaceDisplayFilters } from "@/helpers/workspace-view";

vi.mock("@/services/workspace.service", () => ({
  WorkspaceService: class {
    getViewDetails = vi.fn(async () => ({
      display_filters: { layout: EIssueLayoutTypes.KANBAN, group_by: "project", order_by: "-created_at" },
    }));
  },
}));

describe("workspace view preferences and requests", () => {
  let store: WorkspaceIssuesFilter;
  const refresh = vi.fn();
  const persist = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    store = new WorkspaceIssuesFilter({
      globalViewId: "all-issues",
      currentUserId: "user-id",
      workspaceIssues: { fetchIssuesWithExistingPagination: refresh },
    } as unknown as IIssueRootStore);
    store.handleIssuesLocalFilters.get = vi.fn(() => ({}));
    store.handleIssuesLocalFilters.set = persist;
  });

  async function update(filters: IIssueDisplayFilterOptions) {
    await store.updateFilters("workspace", undefined, EIssueFilterType.DISPLAY_FILTERS, filters, "all-issues");
  }

  it("keeps the existing spreadsheet default and restores a locally selected layout", async () => {
    await store.fetchFilters("workspace", "all-issues");
    expect(store.issueFilters?.displayFilters?.layout).toBe(EIssueLayoutTypes.SPREADSHEET);
    await update({ layout: EIssueLayoutTypes.LIST, group_by: "project" });
    expect(persist).toHaveBeenCalledWith(
      expect.anything(),
      EIssueFilterType.DISPLAY_FILTERS,
      "workspace",
      undefined,
      "all-issues",
      expect.objectContaining({
        display_filters: expect.objectContaining({ layout: "list", group_by: "project" }),
      })
    );
    store.handleIssuesLocalFilters.get = vi.fn(() => ({ display_filters: { layout: "list", group_by: "project" } }));
    await store.fetchFilters("workspace", "all-issues");
    expect(store.getAppliedFilters("all-issues")?.group_by).toBe("project_id");
  });

  it("restores a saved workspace view's layout and project grouping", async () => {
    await store.fetchFilters("workspace", "saved-view");
    expect(store.getAppliedFilters("saved-view")?.group_by).toBe("project_id");
    expect(store.filters["saved-view"].displayFilters?.layout).toBe("kanban");
  });

  it("uses priority when switching an ungrouped view to a board", async () => {
    await store.fetchFilters("workspace", "all-issues");
    await update({ layout: EIssueLayoutTypes.KANBAN });
    expect(store.issueFilters?.displayFilters?.group_by).toBe("priority");
    expect(refresh).toHaveBeenCalledWith("workspace", "all-issues", "mutation");
  });

  it("removes a duplicate subgroup when switching to a board", async () => {
    await store.fetchFilters("workspace", "all-issues");
    await update({ layout: EIssueLayoutTypes.KANBAN, group_by: "project", sub_group_by: "project" });
    expect(store.issueFilters?.displayFilters?.sub_group_by).toBeNull();
  });

  it("requests the next page of one project without losing rich filters or the static view condition", async () => {
    await store.fetchFilters("workspace", "assigned");
    await store.updateFilters(
      "workspace",
      undefined,
      EIssueFilterType.DISPLAY_FILTERS,
      { layout: EIssueLayoutTypes.LIST, group_by: "project" },
      "assigned"
    );
    store.filters.assigned.richFilters = { and: [] };
    const params = store.getFilterParams(
      { canGroup: true, perPageCount: 50 },
      "assigned",
      "50:1:0",
      "project-id",
      undefined
    );
    expect(params).toMatchObject({
      project: "project-id",
      assignees: "user-id",
      cursor: "50:1:0",
      filters: '{"and":[]}',
    });
    expect(params.group_by).toBeUndefined();
  });

  it("groups calendar requests by due date and strips stale board grouping", async () => {
    await store.fetchFilters("workspace", "all-issues");
    await update({ layout: EIssueLayoutTypes.CALENDAR, group_by: "project", sub_group_by: "priority" });
    const params = store.getFilterParams(
      { canGroup: true, perPageCount: 4, groupedBy: "target_date", after: "2026-09-01", before: "2026-10-01" },
      "all-issues",
      undefined,
      undefined,
      undefined
    );
    expect(params).toMatchObject({ group_by: "target_date", target_date: "2026-09-01;after,2026-10-01;before" });
    expect(params.sub_group_by).toBeUndefined();
  });

  it.each([EIssueLayoutTypes.SPREADSHEET, EIssueLayoutTypes.GANTT])(
    "fetches flat results for %s after a grouped layout",
    async (layout) => {
      await store.fetchFilters("workspace", "all-issues");
      await update({ layout, group_by: "project", sub_group_by: "priority" });
      const params = store.getAppliedFilters("all-issues");
      expect(params?.group_by).toBeUndefined();
      expect(params?.sub_group_by).toBeUndefined();
    }
  );

  it("provides display options for every available layout", () => {
    for (const layout of Object.values(EIssueLayoutTypes)) {
      expect(ISSUE_DISPLAY_FILTERS_BY_PAGE.my_issues.layoutOptions[layout]).toBeDefined();
    }
    expect(ISSUE_DISPLAY_FILTERS_BY_PAGE.my_issues.layoutOptions.list.display_filters.group_by).toContain("project");
    expect(ISSUE_DISPLAY_FILTERS_BY_PAGE.my_issues.layoutOptions.kanban.display_filters.group_by).toContain("project");
  });

  it("normalizes saved boards without a group and clears duplicate swimlane groups", () => {
    expect(getWorkspaceDisplayFilters({ layout: "kanban", group_by: null }).group_by).toBe("priority");
    expect(
      getWorkspaceDisplayFilters({ layout: "list", group_by: "project", sub_group_by: "project" }, { layout: "kanban" })
        .sub_group_by
    ).toBeNull();
    expect(getWorkspaceDisplayFilters({ layout: "kanban", group_by: "state" }).group_by).toBe("priority");
  });
});
