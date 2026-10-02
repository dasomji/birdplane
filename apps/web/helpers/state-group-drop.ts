import { sortBy } from "lodash-es";
import type { IState, TIssue } from "@plane/types";

/** Resolve shared workflow groups using only the card's own project states. */
export async function resolveStateGroupDrop(
  projectId: string,
  data: Partial<TIssue>,
  fetchStates: (projectId: string) => Promise<IState[]>
): Promise<Partial<TIssue>> {
  if (!data.state__group) return data;
  const states = await fetchStates(projectId);
  const matching = sortBy(
    states.filter((state) => state.project_id === projectId && state.group === data.state__group),
    (state) => -Number(state.default),
    "sequence",
    "id"
  );
  if (!matching[0]) throw new Error("This project has no state in the selected workflow group.");
  return { ...data, state_id: matching[0].id };
}
