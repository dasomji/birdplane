import pytest
from django.utils import timezone

from plane.db.models import Workspace, WorkspaceMember


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_discovery_memberships_and_pagination(api_key_client, create_user):
    for slug, active, deleted in [
        ("a-company", True, False),
        ("b-personal", True, False),
        ("c-inactive", False, False),
        ("d-deleted-member", True, True),
    ]:
        workspace = Workspace.objects.create(name=slug, slug=slug, owner=create_user)
        WorkspaceMember.objects.create(
            workspace=workspace,
            member=create_user,
            role=20,
            is_active=active,
            deleted_at=timezone.now() if deleted else None,
        )
    Workspace.objects.create(name="Unrelated", slug="unrelated", owner=create_user)
    deleted = Workspace.objects.create(name="Deleted", slug="deleted", owner=create_user)
    WorkspaceMember.objects.create(workspace=deleted, member=create_user, role=20)
    Workspace.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())

    url = "/api/v1/workspaces/"
    first = api_key_client.get(url, {"per_page": 1})
    assert first.status_code == 200
    assert first.data["results"][0]["slug"] == "a-company"
    assert set(first.data["results"][0]) == {"id", "name", "slug"}
    assert first.data["next_page_results"]
    second = api_key_client.get(url, {"per_page": 1, "cursor": first.data["next_cursor"]})
    assert second.data["results"][0]["slug"] == "b-personal"
    assert not second.data["next_page_results"]
    assert api_key_client.get(url).data["total_count"] == 2
    assert api_key_client.get(url, {"query": "PERSONAL"}).data["results"][0]["slug"] == "b-personal"
    assert api_key_client.get(url, {"query": "missing"}).data["results"] == []

    WorkspaceMember.objects.filter(workspace__slug="b-personal").update(is_active=False)
    assert api_key_client.get(url).data["total_count"] == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_discovery_requires_valid_key(api_client):
    assert api_client.get("/api/v1/workspaces/").status_code in (401, 403)
    api_client.credentials(HTTP_X_API_KEY="invalid")
    assert api_client.get("/api/v1/workspaces/").status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_discovery_empty_and_read_only(api_key_client):
    assert api_key_client.get("/api/v1/workspaces/").data["results"] == []
    assert api_key_client.post("/api/v1/workspaces/", {}).status_code == 405


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("limit", ["0", "-1", "51", "bad"])
def test_workspace_discovery_rejects_invalid_page_size(api_key_client, limit):
    assert api_key_client.get("/api/v1/workspaces/", {"per_page": limit}).status_code == 400
