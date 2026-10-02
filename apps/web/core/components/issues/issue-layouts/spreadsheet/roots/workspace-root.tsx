/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useEffect } from "react";
import { observer } from "mobx-react";
// plane constants
import { ALL_ISSUES, EIssueFilterType, EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import type { GroupByColumnTypes, IIssueDisplayFilterOptions } from "@plane/types";
import { EIssuesStoreType, EIssueLayoutTypes } from "@plane/types";
// components
import { AllIssueQuickActions } from "@/components/issues/issue-layouts/quick-action-dropdowns";
import { SpreadsheetLayoutLoader } from "@/components/ui/loader/layouts/spreadsheet-layout-loader";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssuesActions } from "@/hooks/use-issues-actions";
import { useWorkspaceIssueProperties } from "@/hooks/use-workspace-issue-properties";
// store
import { IssueLayoutHOC } from "../../issue-layout-HOC";
import type { TRenderQuickActions } from "../../list/list-view-types";
import { getGroupByColumns } from "../../utils";
import { SpreadsheetView } from "../spreadsheet-view";

type Props = {
  isDefaultView: boolean;
  isLoading?: boolean;
  toggleLoading: (value: boolean) => void;
  workspaceSlug: string;
  globalViewId: string;
  routeFilters: {
    [key: string]: string;
  };
  fetchNextPages: () => void;
  globalViewsLoading: boolean;
  issuesLoading: boolean;
};

export const WorkspaceSpreadsheetRoot = observer(function WorkspaceSpreadsheetRoot(props: Props) {
  const { isLoading = false, workspaceSlug, globalViewId, fetchNextPages, issuesLoading } = props;

  // Custom hooks
  useWorkspaceIssueProperties(workspaceSlug);

  // Store hooks
  const {
    issuesFilter: { filters, updateFilters },
    issues: { getIssueLoader, getPaginationData, groupedIssueIds, getGroupIssueCount },
  } = useIssues(EIssuesStoreType.GLOBAL);
  const { fetchIssues, fetchNextIssues, updateIssue, removeIssue, archiveIssue } = useIssuesActions(
    EIssuesStoreType.GLOBAL
  );
  const { allowPermissions } = useUserPermissions();

  // Derived values
  const issueFilters = globalViewId ? filters?.[globalViewId.toString()] : undefined;

  const groupBy = issueFilters?.displayFilters?.group_by;
  useEffect(() => {
    fetchIssues("init-loader", { canGroup: !!groupBy, perPageCount: groupBy ? 50 : 100 });
  }, [fetchIssues, groupBy, globalViewId]);

  // Permission checker
  const canEditProperties = useCallback(
    (projectId: string | undefined) => {
      if (!projectId) return false;
      return allowPermissions(
        [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        EUserPermissionsLevel.PROJECT,
        workspaceSlug.toString(),
        projectId
      );
    },
    [allowPermissions, workspaceSlug]
  );

  // Display filters handler
  const handleDisplayFiltersUpdate = useCallback(
    (updatedDisplayFilter: Partial<IIssueDisplayFilterOptions>) => {
      if (!workspaceSlug || !globalViewId) return;

      updateFilters(
        workspaceSlug.toString(),
        undefined,
        EIssueFilterType.DISPLAY_FILTERS,
        { ...updatedDisplayFilter },
        globalViewId.toString()
      );
    },
    [updateFilters, workspaceSlug, globalViewId]
  );

  // Quick actions renderer
  const renderQuickActions: TRenderQuickActions = useCallback(
    ({ issue, parentRef, customActionButton, placement, portalElement }) => (
      <AllIssueQuickActions
        parentRef={parentRef}
        customActionButton={customActionButton}
        issue={issue}
        handleDelete={async () => removeIssue(issue.project_id, issue.id)}
        handleUpdate={async (data) => updateIssue && updateIssue(issue.project_id, issue.id, data)}
        handleArchive={async () => archiveIssue && archiveIssue(issue.project_id, issue.id)}
        portalElement={portalElement}
        readOnly={!canEditProperties(issue.project_id ?? undefined)}
        placements={placement}
      />
    ),
    [canEditProperties, removeIssue, updateIssue, archiveIssue]
  );

  // Loading state
  if ((isLoading && issuesLoading && getIssueLoader() === "init-loader") || !globalViewId || !groupedIssueIds) {
    return <SpreadsheetLayoutLoader />;
  }

  // Computed values
  const groups = groupBy
    ? (
        getGroupByColumns({
          groupBy: groupBy as GroupByColumnTypes,
          includeNone: true,
          isWorkspaceLevel: true,
        }) ?? []
      )
        .map((column) => ({
          id: column.id,
          name: column.name,
          icon: column.icon,
          issueIds: Array.isArray(groupedIssueIds[column.id]) ? (groupedIssueIds[column.id] as string[]) : [],
          count: getGroupIssueCount(column.id, undefined, false) ?? 0,
          canLoadMore: !!getPaginationData(column.id, undefined)?.nextPageResults,
          isLoading: getIssueLoader(column.id) === "pagination",
          loadMore: () => {
            if (!getIssueLoader(column.id)) fetchNextIssues(column.id);
          },
        }))
        .filter(
          (group) => issueFilters?.displayFilters?.show_empty_groups || group.count > 0 || group.issueIds.length > 0
        )
    : undefined;
  const issueIds = groups ? [...new Set(groups.flatMap((group) => group.issueIds))] : groupedIssueIds[ALL_ISSUES];
  const nextPageResults = getPaginationData(ALL_ISSUES, undefined)?.nextPageResults;

  // Render spreadsheet
  return (
    <IssueLayoutHOC layout={EIssueLayoutTypes.SPREADSHEET}>
      <SpreadsheetView
        groups={groups}
        displayProperties={issueFilters?.displayProperties ?? {}}
        displayFilters={issueFilters?.displayFilters ?? {}}
        handleDisplayFilterUpdate={handleDisplayFiltersUpdate}
        issueIds={Array.isArray(issueIds) ? issueIds : []}
        quickActions={renderQuickActions}
        updateIssue={updateIssue}
        canEditProperties={canEditProperties}
        canLoadMoreIssues={!!nextPageResults}
        loadMoreIssues={fetchNextPages}
        isWorkspaceLevel
      />
    </IssueLayoutHOC>
  );
});
