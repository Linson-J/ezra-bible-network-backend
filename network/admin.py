from django.contrib import admin

from .models import AppConfig, DailyVerse, Device, MinistryContent, PrayerRequest, Program, SpecialVerse


class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(AppConfig, SingletonAdmin)
admin.site.register(MinistryContent, SingletonAdmin)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ["title", "day_of_week", "start_time", "end_time", "speaker", "is_active"]
    list_filter = ["day_of_week", "is_active"]
    search_fields = ["title", "speaker"]


@admin.register(DailyVerse)
class DailyVerseAdmin(admin.ModelAdmin):
    list_display = ["day", "reference"]
    search_fields = ["reference", "text"]


@admin.register(SpecialVerse)
class SpecialVerseAdmin(admin.ModelAdmin):
    list_display = ["date", "reference", "note"]


@admin.register(PrayerRequest)
class PrayerRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "phone", "request"]


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["platform", "fcm_token", "last_seen"]
    readonly_fields = ["created_at", "last_seen"]
