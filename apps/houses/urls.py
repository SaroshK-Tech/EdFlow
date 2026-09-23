from django.urls import path

from . import views

app_name = "houses"

urlpatterns = [
    path("", views.HouseListView.as_view(), name="list"),
    path("add/", views.HouseCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", views.HouseUpdateView.as_view(), name="edit"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("points/", views.HousePointListView.as_view(), name="points"),
    path("points/add/", views.HousePointCreateView.as_view(), name="points_add"),
    path("activities/", views.HouseActivityListView.as_view(), name="activities"),
    path("activities/add/", views.HouseActivityCreateView.as_view(), name="activity_add"),
    path("results/add/", views.HouseResultCreateView.as_view(), name="results_add"),
]