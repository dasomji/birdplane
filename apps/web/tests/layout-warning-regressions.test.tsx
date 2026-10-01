// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { action, observable } from "mobx";
import { observer } from "mobx-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { IWorkItemFilterInstance } from "@plane/shared-state";
import type { IIssueFilters } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";
import { HydrateFallback } from "../app/root";
import { WorkItemFiltersHOC } from "@/components/work-item-filters/filters-hoc/base";
import { AppSidebarItem } from "@/components/sidebar/sidebar-item";
import { DropdownButton } from "@/components/dropdowns/buttons";

vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark" }) }));
vi.mock("../app/error", () => ({ CustomErrorComponent: () => null }));
vi.mock("../app/provider", () => ({ AppProvider: ({ children }: { children: React.ReactNode }) => children }));
vi.mock("@/components/common/logo-spinner", () => ({ LogoSpinner: () => createElement("span", null, "Loading") }));
vi.mock("@/hooks/store/work-item-filters/use-work-item-filters", () => ({ useWorkItemFilters: () => filtersStore }));
vi.mock("@/hooks/work-item-filters/use-work-item-filters-config", () => ({
  useWorkItemFiltersConfig: () => ({ areAllConfigsInitialized: true, configs: [] }),
}));

const filters = observable.map<string, IWorkItemFilterInstance>(undefined, { deep: false });
const filtersStore = {
  getFilter: (_entityType: EIssuesStoreType, entityId: string) => filters.get(entityId),
  getOrCreateFilter: vi.fn(
    action(({ entityId }: { entityId: string }) => {
      let filter = filters.get(entityId);
      if (!filter) {
        filter = {
          configManager: { setAreConfigsReady: vi.fn(), registerAll: vi.fn() },
        } as unknown as IWorkItemFilterInstance;
        filters.set(entityId, filter);
      }
      return filter;
    })
  ),
  deleteFilter: vi.fn(action((_entityType: EIssuesStoreType, entityId: string) => filters.delete(entityId))),
};
const initialWorkItemFilters = { richFilters: {} } as IIssueFilters;
const updateFilters = vi.fn();

function FilterRoot({ entityId = "all-issues" }: { entityId?: string }) {
  return (
    <WorkItemFiltersHOC
      entityType={EIssuesStoreType.GLOBAL}
      entityId={entityId}
      workspaceSlug="workspace"
      filtersToShowByLayout={[]}
      initialWorkItemFilters={initialWorkItemFilters}
      updateFilters={updateFilters}
    >
      <span>Filter ready</span>
    </WorkItemFiltersHOC>
  );
}

const FilterSubscriber = observer(function FilterSubscriber() {
  return createElement(
    "span",
    null,
    filtersStore.getFilter(EIssuesStoreType.GLOBAL, "all-issues") ? "Ready" : "Waiting"
  );
});

let root: Root;
let container: HTMLDivElement;

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { configurable: true, value: true });
  filters.clear();
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

describe("startup hydration", () => {
  it("matches the empty prerendered fallback even when the browser theme is already resolved", () => {
    expect(renderToString(createElement(HydrateFallback))).toBe("<div></div>");
  });

  it("shows the loading indicator after the first client commit", async () => {
    await act(() => root.render(createElement(HydrateFallback)));
    expect(container.textContent).toBe("Loading");
  });

  it("hydrates the server fallback without a mismatch when the theme is already resolved", async () => {
    await act(() => root.unmount());
    container.innerHTML = renderToString(createElement(HydrateFallback));
    const onRecoverableError = vi.fn();
    await act(() => {
      root = hydrateRoot(container, createElement(HydrateFallback), { onRecoverableError });
    });
    expect(onRecoverableError).not.toHaveBeenCalled();
    expect(container.textContent).toBe("Loading");
  });
});

describe("sidebar menu controls", () => {
  it("renders one button when a menu supplies its own trigger", () => {
    const markup = renderToString(
      <button type="button">
        <AppSidebarItem variant="content" item={{ label: "Help", icon: <span>?</span> }} />
      </button>
    );
    expect(markup.match(/<button/g)).toHaveLength(1);
    expect(markup).toContain("Help");
  });

  it("keeps standalone sidebar actions as native buttons", async () => {
    const onClick = vi.fn();
    await act(() => root.render(<AppSidebarItem variant="button" item={{ label: "Help", onClick }} />));
    const button = container.querySelector("button");
    expect(button).not.toBeNull();
    await act(() => button?.click());
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("work item dropdown triggers", () => {
  it.each(["border-with-text", "background-with-text", "transparent-with-text"] as const)(
    "keeps %s content inside the dropdown's single native button",
    (variant) => {
      const markup = renderToString(
        <button type="button">
          <DropdownButton variant={variant} isActive={false} tooltipHeading="State" showTooltip>
            Todo
          </DropdownButton>
        </button>
      );
      expect(markup.match(/<button/g)).toHaveLength(1);
      expect(markup).toContain("Todo");
    }
  );
});

describe("workspace filter lifecycle", () => {
  it("does not register observable filters during rendering", () => {
    renderToString(createElement(FilterRoot));
    expect(filtersStore.getOrCreateFilter).not.toHaveBeenCalled();
    expect(filters.size).toBe(0);
  });

  it("notifies existing subscribers after commit and cleans up on unmount", async () => {
    const consoleError = vi.spyOn(console, "error");
    await act(() => root.render(createElement("div", null, createElement(FilterSubscriber))));
    await act(() =>
      root.render(createElement("div", null, createElement(FilterSubscriber), createElement(FilterRoot)))
    );
    expect(container.textContent).toBe("ReadyFilter ready");
    expect(filters.get("all-issues")?.configManager.registerAll).toHaveBeenCalledWith([]);
    expect(consoleError).not.toHaveBeenCalled();
    await act(() => root.render(null));
    expect(filters.size).toBe(0);
  });

  it("replaces the filter when navigating to another view", async () => {
    await act(() => root.render(createElement(FilterRoot)));
    await act(() => root.render(createElement(FilterRoot, { entityId: "saved-view" })));
    expect(filters.has("all-issues")).toBe(false);
    expect(filters.has("saved-view")).toBe(true);
    expect(container.textContent).toBe("Filter ready");
  });
});
