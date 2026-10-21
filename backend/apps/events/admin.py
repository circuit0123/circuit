from django.contrib import admin

from apps.events.models import Event
from core.adminbase import ReadOnlyAdmin


@admin.register(Event)
class EventAdmin(ReadOnlyAdmin):
    list_display = ("id", "type", "target_type", "target_id", "created_at")
    list_filter = ("type",)
