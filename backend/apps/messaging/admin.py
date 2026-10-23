from django.contrib import admin

from apps.messaging.models import Conversation
from core.adminbase import ReadOnlyAdmin


@admin.register(Conversation)
class ConversationAdmin(ReadOnlyAdmin):
    """Who is talking to whom, never what they said. Moderators read a message only when someone reports it."""

    list_display = ("id", "member_a", "member_b", "status", "last_message_at")
    list_filter = ("status",)
