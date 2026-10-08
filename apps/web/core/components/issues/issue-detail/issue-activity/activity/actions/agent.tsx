/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Bot } from "lucide-react";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { IssueActivityBlockComponent } from "./helpers/activity-block";

export const IssueAgentActivity = observer(function IssueAgentActivity(props: {
  activityId: string;
  ends: "top" | "bottom" | undefined;
}) {
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const activity = getActivityById(props.activityId);
  if (!activity) return null;
  return (
    <IssueActivityBlockComponent icon={<Bot className="size-3.5 text-secondary" />} {...props}>
      {activity.new_value ? (
        <>
          assigned the AI agent <span className="font-medium text-primary">{activity.new_value}</span>.
        </>
      ) : (
        <>
          removed the AI agent <span className="font-medium text-primary">{activity.old_value}</span>.
        </>
      )}
    </IssueActivityBlockComponent>
  );
});
