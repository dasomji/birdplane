// @vitest-environment jsdom
import React, { act } from "react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { IWorkspaceView } from "@plane/types";
import { EIssueLayoutTypes } from "@plane/types";
import { WorkspaceViewForm } from "@/components/workspace/views/form";

vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@plane/propel/button", () => ({
  Button: ({ loading: _loading, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) => (
    <button {...props} />
  ),
}));
vi.mock("@plane/ui", () => ({
  Input: React.forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { hasError?: boolean }>(
    ({ hasError: _hasError, ...props }, ref) => <input {...props} ref={ref} />
  ),
  TextArea: ({
    hasError: _hasError,
    ...props
  }: TextareaHTMLAttributes<HTMLTextAreaElement> & { hasError?: boolean }) => <textarea {...props} />,
}));
vi.mock("@/components/issues/issue-layouts/filters", () => ({
  LayoutSelection: ({ selectedLayout }: { selectedLayout: string }) => (
    <output data-testid="layout">{selectedLayout}</output>
  ),
  FiltersDropdown: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DisplayFiltersSelection: () => null,
}));
vi.mock("@/components/work-item-filters/filters-hoc/workspace-level", () => ({
  WorkspaceLevelWorkItemFiltersHOC: () => null,
}));
vi.mock("@/components/work-item-filters/filters-row", () => ({ WorkItemFiltersRow: () => null }));

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

describe("workspace view form snapshot", () => {
  it("uses the current layout and grouping when a mounted Save as dialog receives its snapshot", async () => {
    const submit = vi.fn(async (_data: Partial<IWorkspaceView>) => {});
    const props = { workspaceSlug: "personal", handleClose: vi.fn(), handleFormSubmit: submit };
    await act(async () => root.render(<WorkspaceViewForm {...props} />));
    const preLoadedData = {
      name: "Workflow board",
      display_filters: { layout: EIssueLayoutTypes.KANBAN, group_by: "state_detail.group" as const },
    };
    await act(async () => root.render(<WorkspaceViewForm {...props} preLoadedData={preLoadedData} />));
    expect(container.querySelector("[data-testid=layout]")?.textContent).toBe("kanban");
    await act(async () =>
      container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
    );
    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Workflow board", display_filters: preLoadedData.display_filters })
    );
  });
});
