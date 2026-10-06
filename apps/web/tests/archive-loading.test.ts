import { describe, expect, it, vi } from "vitest";
import { CycleStore } from "@/store/cycle.store";
import { ModulesStore } from "@/store/module.store";
import type { CoreRootStore } from "@/store/root.store";

const projectId = "project";
const rootStore = {
  router: { projectId },
  cycleFilter: { getArchivedFiltersByProjectId: () => ({}), archivedCyclesSearchQuery: "" },
  moduleFilter: {
    getArchivedFiltersByProjectId: () => ({}),
    getDisplayFiltersByProjectId: () => ({}),
    archivedModulesSearchQuery: "",
  },
} as unknown as CoreRootStore;

describe("direct archive navigation", () => {
  it("finishes loading an empty cycle archive without marking regular cycles as fetched", async () => {
    const store = new CycleStore(rootStore);
    vi.spyOn(store.cycleArchiveService, "getArchivedCycles").mockResolvedValue([]);
    expect(store.currentProjectArchivedCycleIds).toBeNull();
    await store.fetchArchivedCycles("workspace", projectId);
    expect(store.currentProjectArchivedCycleIds).toEqual([]);
    expect(store.getFilteredArchivedCycleIds(projectId)).toEqual([]);
    expect(store.currentProjectCycleIds).toBeNull();
  });

  it("finishes loading an empty module archive without marking regular modules as fetched", async () => {
    const store = new ModulesStore(rootStore);
    vi.spyOn(store.moduleArchiveService, "getArchivedModules").mockResolvedValue([]);
    expect(store.projectArchivedModuleIds).toBeNull();
    await store.fetchArchivedModules("workspace", projectId);
    expect(store.projectArchivedModuleIds).toEqual([]);
    expect(store.getFilteredArchivedModuleIds(projectId)).toEqual([]);
    expect(store.projectModuleIds).toBeNull();
  });
});
