// @vitest-environment jsdom
import React, { act, createContext } from "react";
import { createRoot } from "react-dom/client";
import { observable, runInAction } from "mobx";
import { expect, it, vi } from "vitest";
import type { IIssueFilters } from "@plane/types";
import { AllIssueLayoutRoot } from "@/components/issues/issue-layouts/roots/all-issue-layout-root";

const mocks = vi.hoisted(() => ({ filters: {} as Record<string, IIssueFilters> }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "personal", globalViewId: "saved" }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("swr", () => ({ default: () => ({ isLoading: false }) }));
vi.mock("@plane/propel/empty-state", () => ({ EmptyStateDetailed: () => null }));
vi.mock("@/components/issues/peek-overview", () => ({ IssuePeekOverview: () => null }));
vi.mock("@/components/ui/loader/layouts/spreadsheet-layout-loader", () => ({ SpreadsheetLayoutLoader: () => null }));
vi.mock("@/components/views/helper", () => ({ WorkspaceActiveLayout: () => null }));
vi.mock("@/components/work-item-filters/filters-row", () => ({ WorkItemFiltersRow: () => null }));
vi.mock("@/hooks/use-issue-layout-store", () => ({ IssuesStoreContext: createContext(null) }));
vi.mock("@/hooks/use-app-router", () => ({ useAppRouter: () => ({}) }));
vi.mock("@/hooks/use-workspace-issue-properties", () => ({ useWorkspaceIssueProperties: () => {} }));
vi.mock("@/hooks/store/use-global-view", () => ({ useGlobalView: () => ({ getViewDetailsById: () => savedView }) }));
const savedView = { rich_filters: {}, display_filters: { layout: "kanban", group_by: "project" } };
vi.mock("@/hooks/store/use-issues", () => ({
  useIssues: () => ({ issuesFilter: { filters: mocks.filters, updateFilterExpression: vi.fn() }, issues: {} }),
}));
vi.mock("@/components/work-item-filters/filters-hoc/workspace-level", () => ({
  WorkspaceLevelWorkItemFiltersHOC: ({ initialWorkItemFilters }: { initialWorkItemFilters: IIssueFilters }) => (
    <output>{JSON.stringify(initialWorkItemFilters.displayFilters)}</output>
  ),
}));
it("passes the current layout and grouping to Save as after settings change on the same view", async () => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.filters = observable({ saved: { displayFilters: { layout: "kanban", group_by: "project" } } as IIssueFilters });
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(<AllIssueLayoutRoot isDefaultView={false} toggleLoading={vi.fn()} />));
    await act(async () =>
      runInAction(() => {
        mocks.filters.saved.displayFilters = { layout: "spreadsheet", group_by: "project" };
      })
    );
    expect(JSON.parse(container.textContent!)).toMatchObject({ layout: "spreadsheet", group_by: "project" });
    await act(async () =>
      runInAction(() => {
        mocks.filters.saved.displayFilters = { layout: "spreadsheet", group_by: "priority" };
      })
    );
    expect(JSON.parse(container.textContent!)).toMatchObject({ layout: "spreadsheet", group_by: "priority" });
  } finally {
    await act(async () => root.unmount());
    container.remove();
  }
});
