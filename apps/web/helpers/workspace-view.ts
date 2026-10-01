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

  const groupingOptions = options[filters.layout].display_filters;
  if (groupingOptions.group_by && !groupingOptions.group_by.includes(filters.group_by ?? null)) {
    filters.group_by = filters.layout === EIssueLayoutTypes.KANBAN ? "priority" : null;
  }
  if (groupingOptions.sub_group_by && !groupingOptions.sub_group_by.includes(filters.sub_group_by ?? null)) {
    filters.sub_group_by = null;
  }
  if (filters.group_by === null || filters.group_by === filters.sub_group_by) filters.sub_group_by = null;
  return filters;
}
