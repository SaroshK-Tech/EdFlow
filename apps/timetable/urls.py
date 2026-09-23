from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("list/", views.TimetableListView.as_view(), name="list"),
    path("generate/", views.TimetableGenerateView.as_view(), name="generate"),
    path("result/<int:pk>/", views.TimetableResultView.as_view(), name="result"),
    path("print/<int:pk>/", views.TimetablePrintView.as_view(), name="print"),
    path("cell/<int:pk>/", views.CellEditView.as_view(), name="cell"),
    path("cell/<int:pk>/move/", views.MoveCellView.as_view(), name="move_cell"),
    path("regenerate/<int:pk>/", views.TimetableRegenerateView.as_view(), name="regenerate"),
    path("entries/<int:pk>/lock/", views.LockCellView.as_view(), name="lock_cell"),
    path("entries/<int:pk>/unlock/", views.UnlockCellView.as_view(), name="unlock_cell"),
    path("approve/<int:pk>/", views.TimetableApproveView.as_view(), name="approve"),
    path("publish/<int:pk>/", views.TimetablePublishView.as_view(), name="publish"),
    path("archive/<int:pk>/", views.TimetableArchiveView.as_view(), name="archive"),
    path("delete/<int:pk>/", views.TimetableDeleteView.as_view(), name="delete"),
    path("<int:pk>/", views.TimetableDetailView.as_view(), name="detail"),
]