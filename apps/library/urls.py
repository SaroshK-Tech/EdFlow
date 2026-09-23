from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.BookListView.as_view(), name="list"),
    path("add/", views.BookCreateView.as_view(), name="book_add"),
    path("<int:pk>/", views.BookDetailView.as_view(), name="book_detail"),
    path("<int:pk>/edit/", views.BookUpdateView.as_view(), name="book_edit"),
    path("<int:pk>/delete/", views.BookDeleteView.as_view(), name="book_delete"),
    path("authors/add/", views.AuthorCreateView.as_view(), name="author_add"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category_add"),
    path("publishers/add/", views.PublisherCreateView.as_view(), name="publisher_add"),
    path("copies/", views.CopyListView.as_view(), name="copies"),
    path("copies/add/", views.CopyCreateView.as_view(), name="copy_add"),
    path("copies/<int:pk>/delete/", views.CopyDeleteView.as_view(), name="copy_delete"),
    path("members/", views.MemberListView.as_view(), name="members"),
    path("members/add/", views.MemberCreateView.as_view(), name="member_add"),
    path("members/<int:pk>/edit/", views.MemberUpdateView.as_view(), name="member_edit"),
    path("issue/", views.issue_copy, name="issue"),
    path("returns/", views.returns_list, name="returns"),
    path("returns/<int:pk>/return/", views.return_issue, name="return"),
    path("returns/<int:pk>/renew/", views.renew_issue, name="renew"),
    path("copy/<int:copy_pk>/lost/", views.lost_copy, name="lost"),
    path("copy/<int:copy_pk>/damaged/", views.damaged_copy, name="damaged"),
    path("fines/", views.FineListView.as_view(), name="fines"),
    path("fines/<int:pk>/pay/", views.fine_pay, name="fine_pay"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
]