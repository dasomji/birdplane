# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date

import pytest

from plane.db.models import Issue, IssueAssignee, IssueLabel, Label, Project, ProjectMember, State


@pytest.fixture
def view_projects(workspace, create_user):
    projects = []
    for index in range(3):
        project = Project.objects.create(name=f"View project {index}", identifier=f"VP{index}", workspace=workspace)
        state = State.objects.create(name="Todo", group="unstarted", project=project, workspace=workspace, default=True)
        if index < 2:
            ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
        for issue_index in range(3):
            Issue.objects.create(
                name=f"Item {index}-{issue_index}",
                project=project,
                workspace=workspace,
                created_by=create_user,
                state=state,
                priority="high",
                target_date=date(2026, 9, 15),
            )
        projects.append(project)
    return projects


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceViewLayouts:
    def test_flat_results_remain_available(self, session_client, workspace, view_projects):
        response = session_client.get(f"/api/workspaces/{workspace.slug}/issues/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 6
        assert all(str(issue["project_id"]) != str(view_projects[2].id) for issue in response.data["results"])

    def test_project_groups_have_independent_pagination_and_do_not_leak_private_projects(
        self,
        session_client,
        workspace,
        view_projects,
    ):
        url = f"/api/workspaces/{workspace.slug}/issues/"
        response = session_client.get(url, {"group_by": "project_id", "per_page": 2})
        assert response.status_code == 200
        groups = response.data["results"]
        assert set(groups) == {str(project.id) for project in view_projects[:2]}
        for group in groups.values():
            assert len(group["results"]) == 2
            assert group["total_results"] == 3

        next_page = session_client.get(
            url,
            {
                "project": str(view_projects[0].id),
                "per_page": 2,
                "cursor": "2:1:0",
            },
        )
        assert next_page.status_code == 200
        assert len(next_page.data["results"]) == 1
        assert str(next_page.data["results"][0]["project_id"]) == str(view_projects[0].id)
        assert next_page.data["results"][0]["id"] not in {
            issue["id"] for issue in groups[str(view_projects[0].id)]["results"]
        }

    def test_board_can_group_projects_into_priority_swimlanes(self, session_client, workspace, view_projects):
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/issues/",
            {
                "group_by": "project_id",
                "sub_group_by": "priority",
            },
        )
        assert response.status_code == 200
        assert set(response.data["results"]) == {str(project.id) for project in view_projects[:2]}
        for group in response.data["results"].values():
            assert len(group["results"]["high"]["results"]) == 3

    def test_calendar_groups_due_dates_within_the_requested_range(self, session_client, workspace, view_projects):
        Issue.objects.create(
            name="Outside range", workspace=workspace, project=view_projects[0], target_date=date(2026, 10, 15)
        )
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/issues/",
            {
                "group_by": "target_date",
                "target_date": "2026-09-01;after,2026-10-01;before",
                "per_page": 4,
            },
        )
        assert response.status_code == 200
        assert set(response.data["results"]) == {"2026-09-15"}
        group = response.data["results"]["2026-09-15"]
        assert group["total_results"] == 6
        assert len(group["results"]) == 4

    def test_label_group_ids_do_not_leak_private_project_metadata(self, session_client, workspace, view_projects):
        private_label = Label.objects.create(name="Private label", workspace=workspace, project=view_projects[2])
        response = session_client.get(f"/api/workspaces/{workspace.slug}/issues/", {"group_by": "labels__id"})
        assert response.status_code == 200
        assert str(private_label.id) not in response.data["results"]

    def test_project_group_counts_respect_filters(self, session_client, workspace, view_projects):
        Issue.objects.filter(project=view_projects[0]).update(priority="low")
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/issues/",
            {
                "group_by": "project_id",
                "filters": '{"and":[{"priority__exact":"high"}]}',
            },
        )
        assert response.status_code == 200
        assert set(response.data["results"]) == {str(view_projects[1].id)}
        assert response.data["results"][str(view_projects[1].id)]["total_results"] == 3

    @pytest.mark.parametrize("group_by", ["priority", "state__group", "assignees__id", "labels__id"])
    def test_workspace_wide_groups_keep_issue_properties(
        self, session_client, workspace, view_projects, create_user, group_by
    ):
        issue = Issue.objects.filter(project=view_projects[0]).first()
        label = Label.objects.create(name="View label", workspace=workspace, project=view_projects[0])
        IssueLabel.objects.create(issue=issue, label=label, project=view_projects[0], workspace=workspace)
        IssueAssignee.objects.create(issue=issue, assignee=create_user, project=view_projects[0], workspace=workspace)
        response = session_client.get(f"/api/workspaces/{workspace.slug}/issues/", {"group_by": group_by})
        assert response.status_code == 200
        items = [item for group in response.data["results"].values() for item in group["results"]]
        item = next(item for item in items if item["id"] == issue.id)
        assert str(label.id) in {str(value) for value in item["label_ids"]}
        assert str(create_user.id) in {str(value) for value in item["assignee_ids"]}

    @pytest.mark.parametrize(
        "params",
        [
            {"group_by": "created_by__password"},
            {"group_by": "project_id", "sub_group_by": "invalid"},
            {"group_by": "project_id", "sub_group_by": "project_id"},
            {"sub_group_by": "priority"},
        ],
    )
    def test_invalid_grouping_returns_a_client_error(self, session_client, workspace, view_projects, params):
        response = session_client.get(f"/api/workspaces/{workspace.slug}/issues/", params)
        assert response.status_code == 400
