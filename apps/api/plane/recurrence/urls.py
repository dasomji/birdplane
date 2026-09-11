from django.urls import path
from .views import ScheduleView, CatalogView, manager

urlpatterns = [
    path("api/v1/workspaces/<str:slug>/recurring-catalog/", CatalogView.as_view()),
    path("api/birdplane/recurring/", manager, name="birdplane-recurring"),
    path("api/v1/workspaces/<str:slug>/projects/<uuid:project_id>/recurring-tasks/", ScheduleView.as_view()),
    path("api/v1/workspaces/<str:slug>/projects/<uuid:project_id>/recurring-tasks/<uuid:pk>/", ScheduleView.as_view()),
]
