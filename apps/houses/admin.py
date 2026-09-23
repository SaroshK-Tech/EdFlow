from django.contrib import admin

from .models import House, HouseActivity, HousePoint, HouseResult


@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "captain", "staff_coordinator")
    search_fields = ("name", "motto")


@admin.register(HousePoint)
class HousePointAdmin(admin.ModelAdmin):
    list_display = ("house", "student", "date", "points", "reason", "awarded_by")
    list_filter = ("house", "date")
    search_fields = ("house__name", "reason")


@admin.register(HouseActivity)
class HouseActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "house", "date", "kind")
    list_filter = ("kind", "date")
    search_fields = ("name",)


@admin.register(HouseResult)
class HouseResultAdmin(admin.ModelAdmin):
    list_display = ("activity", "house", "rank", "points_awarded")
    list_filter = ("activity", "house")