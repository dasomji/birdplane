// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BreadcrumbNavigationSearchDropdown } from "@plane/ui";

const navigationItems = [
  { value: "all-issues", query: "All issues", content: "All issues" },
  { value: "saved-view", query: "Saved board", content: "Saved board" },
];
let root: Root;
let container: HTMLDivElement;

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { configurable: true, value: true });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(() => root.unmount());
  container.remove();
});

describe("breadcrumb navigation controls", () => {
  it("uses one native button for the current view's dropdown", async () => {
    await act(() =>
      root.render(
        <BreadcrumbNavigationSearchDropdown
          title="All issues"
          selectedItem="all-issues"
          navigationItems={navigationItems}
          isLast
        />
      )
    );
    expect(container.querySelectorAll("button")).toHaveLength(1);
    expect(container.querySelector("button button")).toBeNull();
  });

  it("keeps parent navigation and dropdown actions on separate buttons", async () => {
    const handleOnClick = vi.fn();
    await act(() =>
      root.render(
        <BreadcrumbNavigationSearchDropdown
          title="Views"
          selectedItem="all-issues"
          navigationItems={navigationItems}
          handleOnClick={handleOnClick}
        />
      )
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(2);
    expect(container.querySelector("button button")).toBeNull();
    await act(() => buttons[0].click());
    expect(handleOnClick).toHaveBeenCalledOnce();
    expect(document.querySelector("[role='listbox']")).toBeNull();
    await act(() => buttons[1].click());
    expect(document.querySelector("[role='listbox']")).not.toBeNull();
    expect(handleOnClick).toHaveBeenCalledOnce();
  });
});
