from django.db import models
from django.db.models import F, Q


class Conversation(models.Model):
    """Two members. `request` = started by someone the other is not connected to; it needs accepting first."""

    class Status(models.TextChoices):
        REQUEST = "request"
        ACTIVE = "active"
        BLOCKED = "blocked"

    member_a = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="conversations_a")
    member_b = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="conversations_b")
    started_by = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    declined_by = models.ForeignKey(
        "accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # the person a request was sent to said "no thanks": gone for them, still a quiet request for the sender
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["member_a", "member_b"], name="conversation_unique_pair"),
            models.CheckConstraint(condition=Q(member_a__lt=F("member_b")), name="conversation_ordered"),
        ]
        indexes = [models.Index(fields=["member_b"]), models.Index(fields=["-last_message_at"])]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="messages_sent")
    body = models.CharField(max_length=2000, blank=True)
    image = models.OneToOneField("social.MediaUpload", null=True, blank=True, on_delete=models.SET_NULL, related_name="message")
    read_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)  # a moderator took it down; the body is hidden from both sides
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "-id"]), models.Index(fields=["sender"])]
