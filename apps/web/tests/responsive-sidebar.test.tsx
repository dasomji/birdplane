// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectAppSidebar } from "@/app/(all)/[workspaceSlug]/(projects)/_sidebar";

const mocks = vi.hoisted(() => ({
  size: [390, 844],
  collapsed: false,
  toggle: vi.fn(),
}));
vi.mock("mobx-react", () => ({ observer: (component: unknown) => component }));
vi.mock("next/navigation", () => ({ useParams: () => ({ workspaceSlug: "audit" }), usePathname: () => "/audit" }));
vi.mock("@plane/hooks", () => ({
  useLocalStorage: () => ({ storedValue: 250, setValue: vi.fn() }),
  usePlatformOS: () => ({ isMobile: false }),
  useOutsideClickDetector: () => {},
}));
vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/hooks/use-window-size", () => ({ default: () => mocks.size }));
vi.mock("@/hooks/store/use-app-theme", () => ({
  useAppTheme: () => ({
    sidebarCollapsed: mocks.collapsed,
    toggleSidebar: mocks.toggle,
    toggleSidebarPeek: vi.fn(),
  }),
}));
vi.mock("@/app/(all)/[workspaceSlug]/(projects)/sidebar", async () => {
  const { SidebarWrapper } = await import("@/components/sidebar/sidebar-wrapper");
  return {
    AppSidebar: () => (
      <SidebarWrapper title="Projects">
        <div>Navigation</div>
      </SidebarWrapper>
    ),
  };
});
vi.mock("@/app/(all)/[workspaceSlug]/(projects)/extended-sidebar", () => ({ ExtendedAppSidebar: () => null }));
vi.mock("@/components/navigation/customize-navigation-dialog", () => ({ CustomizeNavigationDialog: () => null }));
vi.mock("@/components/workspace/edition-badge", () => ({ WorkspaceEditionBadge: () => null }));
vi.mock("@/components/sidebar/sidebar-toggle-button", () => ({ AppSidebarToggleButton: () => null }));
vi.mock("@plane/propel/icons", () => ({ PreferencesIcon: () => null }));
vi.mock("@plane/propel/icon-button", () => ({ IconButton: () => null }));
vi.mock("@plane/propel/scrollarea", () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.collapsed = false;
  mocks.size = [390, 844];
  mocks.toggle.mockReset().mockImplementation((value?: boolean) => {
    mocks.collapsed = value ?? !mocks.collapsed;
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
describe("responsive project sidebar", () => {
  it.each([390, 768])(
    "keeps navigation collapsed at %ipx when the main and peek sidebars mount together",
    async (width) => {
      mocks.size = [width, 844];
      await act(async () => root.render(<ProjectAppSidebar />));
      expect(mocks.collapsed).toBe(true);
      expect(mocks.toggle.mock.calls.every(([value]) => value === true)).toBe(true);
    }
  );
  it("preserves an expanded desktop sidebar", async () => {
    mocks.size = [1280, 900];
    await act(async () => root.render(<ProjectAppSidebar />));
    expect(mocks.collapsed).toBe(false);
  });
  it("allows opening navigation after the viewport has settled and closes it with the backdrop", async () => {
    await act(async () => root.render(<ProjectAppSidebar />));
    mocks.collapsed = false;
    await act(async () => root.render(<ProjectAppSidebar />));
    expect(mocks.collapsed).toBe(false);
    const backdrop = container.querySelector<HTMLButtonElement>('[aria-label="Close navigation sidebar"]');
    expect(backdrop).not.toBeNull();
    await act(async () => backdrop!.click());
    expect(mocks.collapsed).toBe(true);
    await act(async () => root.render(<ProjectAppSidebar />));
    expect(container.querySelector<HTMLElement>("#main-sidebar")?.inert).toBe(true);
    expect(container.querySelector('[aria-label="Sidebar peek view"]')?.getAttribute("aria-hidden")).toBe("true");
  });
  it("keeps manually opened navigation open when only the viewport height changes", async () => {
    await act(async () => root.render(<ProjectAppSidebar />));
    mocks.collapsed = false;
    mocks.size = [390, 600];
    await act(async () => root.render(<ProjectAppSidebar />));
    expect(mocks.collapsed).toBe(false);
  });
});
