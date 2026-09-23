from django.urls import path

from . import views

app_name = "results"

urlpatterns = [
    path("", views.ExamResultListView.as_view(), name="list"),
    path("<int:pk>/", views.ResultListView.as_view(), name="detail"),
    path("<int:pk>/generate/", views.result_generate, name="generate"),
    path("<int:pk>/sheet/", views.ResultSheetView.as_view(), name="sheet"),
    path("<int:pk>/sheet.pdf", views.ResultSheetPdfView.as_view(), name="sheet_pdf"),
    path("<int:pk>/tabulation/<int:class_pk>/", views.TabulationView.as_view(), name="tabulation"),
    path("<int:pk>/report-card/<int:student_pk>/", views.ReportCardView.as_view(), name="report_card"),
    path(
        "<int:pk>/report-card/<int:student_pk>/pdf/",
        views.ReportCardPdfView.as_view(),
        name="report_card_pdf",
    ),
]
