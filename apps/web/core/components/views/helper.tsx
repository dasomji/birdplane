/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { EIssueLayoutTypes } from "@plane/types";
import { BaseCalendarRoot } from "@/components/issues/issue-layouts/calendar/base-calendar-root";
import { BaseGanttRoot } from "@/components/issues/issue-layouts/gantt/base-gantt-root";
import { BaseKanBanRoot } from "@/components/issues/issue-layouts/kanban/base-kanban-root";
import { BaseListRoot } from "@/components/issues/issue-layouts/list/base-list-root";
import { AllIssueQuickActions } from "@/components/issues/issue-layouts/quick-action-dropdowns";
import { WorkspaceSpreadsheetRoot } from "@/components/issues/issue-layouts/spreadsheet/roots/workspace-root";
import { useUserPermissions } from "@/hooks/store/user";

export type TWorkspaceLayoutProps = {
  activeLayout: EIssueLayoutTypes | undefined;
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

export const WorkspaceActiveLayout = observer(function WorkspaceActiveLayout(props: TWorkspaceLayoutProps) {
  const { activeLayout = EIssueLayoutTypes.SPREADSHEET, workspaceSlug, globalViewId } = props;
  const { allowPermissions } = useUserPermissions();
  const canEditPropertiesBasedOnProject = useCallback(
    (projectId: string) =>
      allowPermissions(
        [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        EUserPermissionsLevel.PROJECT,
        workspaceSlug,
        projectId
      ),
    [allowPermissions, workspaceSlug]
  );
  const layoutProps = {
    QuickActions: AllIssueQuickActions,
    canEditPropertiesBasedOnProject,
    viewId: globalViewId,
  };
  switch (activeLayout) {
    case EIssueLayoutTypes.LIST:
      return <BaseListRoot {...layoutProps} />;
    case EIssueLayoutTypes.KANBAN:
      return <BaseKanBanRoot {...layoutProps} />;
    case EIssueLayoutTypes.CALENDAR:
      return <BaseCalendarRoot {...layoutProps} />;
    case EIssueLayoutTypes.GANTT:
      return <BaseGanttRoot viewId={globalViewId} canEditPropertiesBasedOnProject={canEditPropertiesBasedOnProject} />;
    case EIssueLayoutTypes.SPREADSHEET:
    default:
      return <WorkspaceSpreadsheetRoot {...props} />;
  }
});

export type TLayoutSelectionProps = {
  onChange: (layout: EIssueLayoutTypes) => void;
  selectedLayout: EIssueLayoutTypes;
  workspaceSlug: string;
};
