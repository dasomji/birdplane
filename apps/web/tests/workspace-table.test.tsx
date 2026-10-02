// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceSpreadsheetRoot } from "@/components/issues/issue-layouts/spreadsheet/roots/workspace-root";

const mocks = vi.hoisted(() => ({
  fetchIssues: vi.fn(),
  fetchNextIssues: vi.fn(),
  filters: { saved: { displayFilters: { layout: "spreadsheet", group_by: "project", show_empty_groups: false } } },
  ids: { bird: ["a"], other: ["b"] },
}));
vi.mock("@/hooks/use-workspace-issue-properties", () => ({ useWorkspaceIssueProperties: () => {} }));
vi.mock("@/hooks/store/user", () => ({ useUserPermissions: () => ({ allowPermissions: () => true }) }));
vi.mock("@/hooks/store/use-issues", () => ({
  useIssues: () => ({
    issuesFilter: { filters: mocks.filters },
    issues: {
      groupedIssueIds: mocks.ids,
      getIssueLoader: () => undefined,
      getPaginationData: (group: string) => ({ nextPageResults: group === "bird" }),
      getGroupIssueCount: (group: string) => (group === "bird" ? 51 : group === "other" ? 1 : 0),
    },
  }),
}));
vi.mock("@/hooks/use-issues-actions", () => ({ useIssuesActions: () => mocks }));
vi.mock("@/components/issues/issue-layouts/quick-action-dropdowns", () => ({ AllIssueQuickActions: () => null }));
vi.mock("@/components/issues/issue-layouts/issue-layout-HOC", () => ({
  IssueLayoutHOC: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/issues/issue-layouts/utils", () => ({
  getGroupByColumns: () => [
    { id: "bird", name: "Birdplane" },
    { id: "other", name: "Other project" },
    { id: "empty", name: "Empty project" },
  ],
  getDisplayPropertiesCount: () => 0,
}));
vi.mock("@/components/issues/issue-layouts/spreadsheet/issue-row", () => ({
  SpreadsheetIssueRow: ({ issueId }: { issueId: string }) => (
    <tr>
      <td>{issueId}</td>
    </tr>
  ),
}));
vi.mock("@/components/issues/issue-layouts/spreadsheet/spreadsheet-header", () => ({
  SpreadsheetHeader: () => (
    <thead>
      <tr>
        <th>Issues</th>
      </tr>
    </thead>
  ),
}));
vi.mock("@/hooks/use-intersection-observer", () => ({ useIntersectionObserver: () => {} }));
vi.mock("@/hooks/use-issue-layout-store", () => ({
  useIssuesStore: () => ({ issues: { getIssueLoader: () => undefined } }),
}));
vi.mock("@/hooks/use-table-keyboard-navigation", () => ({ useTableKeyboardNavigation: () => undefined }));
vi.mock("@/components/ui/loader/layouts/spreadsheet-layout-loader", () => ({
  SpreadsheetLayoutLoader: () => null,
  SpreadsheetIssueRowLoader: () => null,
}));
vi.mock("@/components/issues/issue-layouts/spreadsheet/spreadsheet-view", async () => {
  const { SpreadsheetTable } = await import("@/components/issues/issue-layouts/spreadsheet/spreadsheet-table");
  return {
    SpreadsheetView: (props: React.ComponentProps<typeof SpreadsheetTable>) => (
      <SpreadsheetTable {...props} containerRef={{ current: null }} spreadsheetColumnsList={[]} />
    ),
  };
});

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.clearAllMocks();
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
const render = async () =>
  act(async () =>
    root.render(
      <WorkspaceSpreadsheetRoot
        isDefaultView={false}
        workspaceSlug="personal"
        globalViewId="saved"
        toggleLoading={() => {}}
        routeFilters={{}}
        fetchNextPages={vi.fn()}
        globalViewsLoading={false}
        issuesLoading={false}
      />
    )
  );
describe("grouped workspace table", () => {
  it("renders group headers and rows, and requests the next page for its own group", async () => {
    await render();
    expect(mocks.fetchIssues).toHaveBeenCalledWith("init-loader", { canGroup: true, perPageCount: 50 });
    expect(container.querySelector('tbody[aria-label="Birdplane"]')?.textContent).toContain("a");
    expect(container.querySelector('tbody[aria-label="Other project"]')?.textContent).toContain("b");
    expect(container.querySelector('tbody[aria-label="Empty project"]')).toBeNull();
    const load = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent === "Load more in Birdplane"
    )!;
    await act(async () => load.click());
    expect(mocks.fetchNextIssues).toHaveBeenCalledWith("bird");
  });
  it("collapses one group without hiding other groups", async () => {
    await render();
    await act(async () => container.querySelector<HTMLButtonElement>('tbody[aria-label="Birdplane"] button')!.click());
    expect(container.querySelector('tbody[aria-label="Birdplane"]')?.textContent).not.toContain("Load more");
    expect(container.querySelector('tbody[aria-label="Other project"]')?.textContent).toContain("b");
    expect(container.querySelector('tbody[aria-label="Birdplane"] button')?.getAttribute("aria-expanded")).toBe(
      "false"
    );
  });
});
