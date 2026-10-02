import { describe, expect, it, vi } from "vitest";
import { EIssuesStoreType } from "@plane/types";
import { useGroupIssuesDragNDrop } from "@/hooks/use-group-dragndrop";

const mocks = vi.hoisted(() => ({ updateIssue: vi.fn(), fetchStates: vi.fn(), toast: vi.fn() }));
vi.mock("next/navigation", () => ({ useParams: () => ({ workspaceSlug: "personal" }) }));
vi.mock("@plane/propel/toast", () => ({ TOAST_TYPE: { ERROR: "error" }, setToast: mocks.toast }));
vi.mock("@/hooks/store/use-project-state", () => ({
  useProjectState: () => ({ fetchProjectStates: mocks.fetchStates }),
}));
vi.mock("@/hooks/store/use-issue-detail", () => ({ useIssueDetail: () => ({ issue: {} }) }));
vi.mock("@/hooks/store/use-issues", () => ({ useIssues: () => ({ issues: {} }) }));
vi.mock("@/hooks/use-issues-actions", () => ({ useIssuesActions: () => ({ updateIssue: mocks.updateIssue }) }));
vi.mock("@/store/issue/helpers/base-issues.store", () => ({
  ISSUE_FILTER_DEFAULT_DATA: { module: "module_ids", cycle: "cycle_id" },
}));
vi.mock("@/components/issues/issue-layouts/utils", () => ({
  handleGroupDragDrop: async (
    _source: unknown,
    _destination: unknown,
    _getIssue: unknown,
    _getIds: unknown,
    update: (project: string, issue: string, data: object, updates: object) => Promise<void>
  ) => update("own", "card", { state__group: "completed", project_id: "own" }, {}),
}));
describe("shared state drop handler", () => {
  it("waits for the project-specific state update", async () => {
    vi.clearAllMocks();
    mocks.fetchStates.mockResolvedValue([{ id: "done-own", group: "completed", project_id: "own", sequence: 1 }]);
    let complete!: () => void;
    mocks.updateIssue.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          complete = resolve;
        })
    );
    const handler = useGroupIssuesDragNDrop(EIssuesStoreType.GLOBAL, "-created_at", "state_detail.group");
    let finished = false;
    const drop = handler(
      { columnId: "started", groupId: "started", id: "card" },
      { columnId: "completed", groupId: "completed", id: undefined }
    ).then(() => {
      finished = true;
      return finished;
    });
    await vi.waitFor(() =>
      expect(mocks.updateIssue).toHaveBeenCalledWith("own", "card", expect.objectContaining({ state_id: "done-own" }))
    );
    expect(mocks.fetchStates).toHaveBeenCalledWith("personal", "own");
    expect(finished).toBe(false);
    complete();
    await drop;
    expect(finished).toBe(true);
  });
  it("reports a missing matching state without updating the card", async () => {
    vi.clearAllMocks();
    mocks.fetchStates.mockResolvedValue([]);
    await useGroupIssuesDragNDrop(
      EIssuesStoreType.GLOBAL,
      "-created_at",
      "state_detail.group"
    )(
      { columnId: "started", groupId: "started", id: "card" },
      { columnId: "completed", groupId: "completed", id: undefined }
    );
    expect(mocks.updateIssue).not.toHaveBeenCalled();
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ message: expect.stringContaining("no state") }));
  });
});
