from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q


class EdFlowMixin(LoginRequiredMixin):
    """Shared behaviour for module views: login + page context."""

    page_title = ""
    page_subtitle = ""
    active_page = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.page_title
        ctx["page_subtitle"] = self.page_subtitle
        ctx["active_page"] = self.active_page
        return ctx


class SearchMixin:
    """Minimal search for list views. Set ``search_fields`` to model attrs."""

    search_fields = []
    search_placeholder = "Search…"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["search_placeholder"] = self.search_placeholder
        return ctx