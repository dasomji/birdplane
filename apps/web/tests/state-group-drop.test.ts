import { describe, expect, it, vi } from "vitest";
import type { IState } from "@plane/types";
import { DRAG_ALLOWED_GROUPS } from "@plane/constants";
import { resolveStateGroupDrop } from "@/helpers/state-group-drop";

const state = (id: string, project_id: string, group: string, sequence = 0, isDefault = false) =>
  ({ id, project_id, group, sequence, default: isDefault }) as IState;

describe("shared workflow drops", () => {
  it("enables dragging shared state groups", () => {
    expect(DRAG_ALLOWED_GROUPS).toContain("state_detail.group");
  });
  it("maps the shared group to the card's project, preferring its default matching state", async () => {
    const fetchStates = vi
      .fn()
      .mockResolvedValue([
        state("foreign", "other", "completed", 0, true),
        state("first", "own", "completed", 1),
        state("default", "own", "completed", 9, true),
        state("active", "own", "started"),
      ]);
    expect(
      await resolveStateGroupDrop("own", { state__group: "completed", project_id: "own" }, fetchStates)
    ).toMatchObject({ project_id: "own", state_id: "default", state__group: "completed" });
    expect(fetchStates).toHaveBeenCalledWith("own");
  });
  it("fails when the card's project has no matching state", async () => {
    await expect(
      resolveStateGroupDrop("own", { state__group: "cancelled" }, async () => [state("foreign", "other", "cancelled")])
    ).rejects.toThrow("no state");
  });
  it("does not fetch states for reordering or another grouping", async () => {
    const fetchStates = vi.fn();
    expect(await resolveStateGroupDrop("own", { priority: "high" }, fetchStates)).toEqual({ priority: "high" });
    expect(fetchStates).not.toHaveBeenCalled();
  });
});
