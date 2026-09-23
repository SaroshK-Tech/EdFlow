from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.core.realtime import notify_user as realtime_notify_user

from .forms import AnnouncementForm, InboxMessageForm
from .models import Announcement, InboxMessage, Notification
from .services import notify_announcement, notify_user, recipients_for


class AnnouncementListView(EdFlowMixin, SearchMixin, ListView):
    model = Announcement
    template_name = "notifications/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 20
    page_title = "Announcements"
    page_subtitle = "Broadcast school-wide announcements"
    active_page = "notifications"
    search_fields = ["title", "body", "message"]
    search_placeholder = "Search announcements…"


class AnnouncementDetailView(EdFlowMixin, DetailView):
    model = Announcement
    template_name = "notifications/announcement_detail.html"
    context_object_name = "announcement"
    page_title = "Announcement"
    active_page = "notifications"


class AnnouncementCreateView(EdFlowMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "notifications/announcement_form.html"
    page_title = "New Announcement"
    page_subtitle = "Broadcast a notice to staff, teachers or a class"
    active_page = "notifications"

    def get_success_url(self):
        return reverse("notifications:announcement_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        targeted = notify_announcement(self.object, actor=self.request.user)
        detail_url = reverse("notifications:announcement_detail", kwargs={"pk": self.object.pk})
        for user in recipients_for(self.object.audience, self.object.klass):
            if user.pk != self.request.user.pk:
                notify_user(
                    user,
                    f"New announcement: {self.object.title}",
                    detail_url,
                    "megaphone",
                    self.object,
                )
                realtime_notify_user(user, "announcement.published", {"title": self.object.title, "url": detail_url})
        audit(
            self.request,
            "notifications",
            object_type="Announcement",
            object_id=self.object.pk,
            details=f"Published announcement '{self.object.title}' ({targeted} notified).",
        )
        messages.success(
            self.request, f"Announcement published — {targeted} user(s) notified."
        )
        return response


class AnnouncementUpdateView(EdFlowMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "notifications/announcement_form.html"
    page_title = "Edit Announcement"
    page_subtitle = "Update the announcement"
    active_page = "notifications"

    def get_success_url(self):
        return reverse("notifications:announcement_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(
            self.request,
            "notifications",
            object_type="Announcement",
            object_id=self.object.pk,
            details="Updated announcement.",
        )
        messages.success(self.request, "Announcement saved.")
        return response


class AnnouncementDeleteView(EdFlowMixin, DeleteView):
    model = Announcement
    template_name = "notifications/confirm_delete.html"
    page_title = "Delete Announcement"
    active_page = "notifications"

    def get_success_url(self):
        return reverse("notifications:announcements")

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        super().post(request, *args, **kwargs)
        audit(
            request,
            "notifications",
            object_type="Announcement",
            object_id=obj.pk,
            details="Deleted announcement.",
        )
        messages.success(request, "Announcement deleted.")
        return self.redirect(request)

    def redirect(self, request):
        from django.shortcuts import redirect

        return redirect("notifications:announcements")


class NotificationListView(EdFlowMixin, ListView):
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notes"
    paginate_by = 30
    page_title = "Notifications"
    page_subtitle = "All notifications for you"
    active_page = "notifications"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        messages.success(request, "All notifications marked as read.")
        return self.render_to_response(self.get_context_data())


class NotificationMarkReadView(EdFlowMixin, View):
    def post(self, request, pk, *args, **kwargs):
        note = get_object_or_404(Notification, pk=pk, recipient=request.user)
        note.is_read = True
        note.save(update_fields=["is_read"])
        return redirect(note.url or "notifications:list")

    def get(self, request, pk, *args, **kwargs):
        return self.post(request, pk, *args, **kwargs)


class InboxListView(EdFlowMixin, ListView):
    """Internal staff messaging — inbox (spec §25)."""

    model = InboxMessage
    template_name = "notifications/inbox_list.html"
    context_object_name = "messages_qs"
    paginate_by = 25
    page_title = "Inbox"
    page_subtitle = "Internal messages — offline-friendly"
    active_page = "notifications"

    def get_queryset(self):
        return InboxMessage.objects.filter(recipient=self.request.user)


class SentListView(EdFlowMixin, ListView):
    model = InboxMessage
    template_name = "notifications/sent_list.html"
    context_object_name = "messages_qs"
    paginate_by = 25
    page_title = "Sent Messages"
    active_page = "notifications"

    def get_queryset(self):
        return InboxMessage.objects.filter(sender=self.request.user)


class InboxComposeView(EdFlowMixin, CreateView):
    model = InboxMessage
    form_class = InboxMessageForm
    template_name = "notifications/inbox_form.html"
    page_title = "New Message"
    page_subtitle = "Send an internal message"
    active_page = "notifications"

    def get_success_url(self):
        return reverse("notifications:sent")

    def form_valid(self, form):
        form.instance.sender = self.request.user
        response = super().form_valid(form)
        audit(
            self.request,
            "notifications",
            object_type="InboxMessage",
            object_id=self.object.pk,
            details="Sent internal message.",
        )
        messages.success(self.request, "Message sent.")
        return response


class InboxDetailView(EdFlowMixin, DetailView):
    model = InboxMessage
    template_name = "notifications/inbox_detail.html"
    context_object_name = "message"
    page_title = "Message"
    active_page = "notifications"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.read_at:
            obj.read_at = __import__("django.utils.timezone", fromlist=["now"]).now()
            obj.save(update_fields=["read_at"])
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reply_url"] = reverse("notifications:compose")
        return ctx