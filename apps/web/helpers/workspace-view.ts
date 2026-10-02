import { ISSUE_DISPLAY_FILTERS_BY_PAGE } from "@plane/constants";
import { EIssueLayoutTypes } from "@plane/types";
import type { IIssueDisplayFilterOptions } from "@plane/types";

/** Keep workspace layouts within their supported grouping and ordering options. */
export function getWorkspaceDisplayFilters(
  current: IIssueDisplayFilterOptions,
  updates: Partial<IIssueDisplayFilterOptions> = {}
): IIssueDisplayFilterOptions {
  const filters = { ...current, ...updates };
  const options = ISSUE_DISPLAY_FILTERS_BY_PAGE.my_issues.layoutOptions;
  if (!filters.layout || !options[filters.layout]) filters.layout = EIssueLayoutTypes.SPREADSHEET;
  if (filters.order_by === "sort_order") filters.order_by = "-created_at";

  if (
    updates.layout === EIssueLayoutTypes.KANBAN &&
    current.layout !== EIssueLayoutTypes.KANBAN &&
    updates.group_by === undefined
  ) {
    filters.group_by = "state_detail.group";
    filters.sub_group_by = null;
  }
  const groupingOptions = options[filters.layout].display_filters;
  if (groupingOptions.group_by && !groupingOptions.group_by.includes(filters.group_by ?? null)) {
    filters.group_by = filters.layout === EIssueLayoutTypes.KANBAN ? "state_detail.group" : null;
  }
  if (groupingOptions.sub_group_by && !groupingOptions.sub_group_by.includes(filters.sub_group_by ?? null)) {
    filters.sub_group_by = null;
  }
  if (
    filters.layout === EIssueLayoutTypes.KANBAN &&
    filters.group_by === "state_detail.group" &&
    (current.layout !== EIssueLayoutTypes.KANBAN || current.group_by !== filters.group_by) &&
    updates.show_empty_groups === undefined
  )
    filters.show_empty_groups = true;
  if (filters.group_by === null || filters.group_by === filters.sub_group_by) filters.sub_group_by = null;
  return filters;
}
