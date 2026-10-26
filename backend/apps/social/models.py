from django.db import models


class MediaUpload(models.Model):
    """One image a member uploaded. Attaching it to a post or message requires owning it, and it can be attached once."""

    class Purpose(models.TextChoices):
        POST = "post"
        MESSAGE = "message"
        AVATAR = "avatar"  # a member's profile photo
        STARTUP_LOGO = "startup_logo"  # a startup's logo, set by its team
        HIGHLIGHT = "highlight"  # a pinned project tile on a member's profile

    class Status(models.TextChoices):
        PENDING = "pending"  # signed URL handed out, bytes not checked yet
        READY = "ready"  # verified, EXIF stripped, resized variants stored

    owner = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="uploads")
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    path = models.CharField(max_length=200, unique=True, help_text="folder in the bucket: <purpose>/<owner id>/<uuid>")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "-created_at"])]


class Post(models.Model):
    """A build log."""

    class Visibility(models.TextChoices):
        EVERYONE = "everyone"
        CONNECTIONS = "connections"
        ORGANISATION = "organisation"

    class Status(models.TextChoices):
        VISIBLE = "visible"
        HIDDEN = "hidden"  # moderators can restore it
        REMOVED = "removed"

    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="posts")
    body = models.CharField(max_length=500, blank=True)
    link = models.URLField(max_length=500, blank=True)
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.CONNECTIONS)
    capabilities = models.ManyToManyField("matching.Capability", related_name="+", blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.VISIBLE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["author", "-created_at"]), models.Index(fields=["status", "-created_at"])]


class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    upload = models.OneToOneField(MediaUpload, on_delete=models.CASCADE, related_name="post_media")
    alt_text = models.CharField(max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["post", "order"], name="postmedia_unique_order")]


class Highlight(models.Model):
    """A project a member pinned to their profile (up to 6, in order). The picture is one of their own `highlight` uploads."""

    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="highlights")
    upload = models.OneToOneField(MediaUpload, on_delete=models.CASCADE, related_name="highlight")
    title = models.CharField(max_length=80)
    link = models.URLField(max_length=500, blank=True)
    alt_text = models.CharField(max_length=300)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["member", "position"], name="highlight_unique_position")]


class Reaction(models.Model):
    class Kind(models.TextChoices):
        HELPFUL = "helpful"
        INTRO_ME = "intro_me"
        LETS_TALK = "lets_talk"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="reactions")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "member", "kind"], name="reaction_unique")]
        indexes = [models.Index(fields=["member"])]


class Reply(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="replies")
    body = models.CharField(max_length=300)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    status = models.CharField(max_length=8, choices=Post.Status.choices, default=Post.Status.VISIBLE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["post", "created_at"]), models.Index(fields=["author"])]


class Follow(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="follows")
    startup = models.ForeignKey("startups.Startup", on_delete=models.CASCADE, related_name="followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "startup"], name="follow_unique")]
        indexes = [models.Index(fields=["startup"])]


class DailyDrop(models.Model):
    """The 3 people shown to a member on one IST calendar day. candidates: [{member_id, reason, is_bridge, outcome}]."""

    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="drops")
    date = models.DateField()
    candidates = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "date"], name="dailydrop_unique")]


class UpdateView(models.Model):
    """The viewer opened this Live wire update (F16). `key` names the update, such as "post:12" or "job:7"."""

    viewer = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="update_views")
    key = models.CharField(max_length=64)
    date = models.DateField()
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["viewer", "key"], name="updateview_viewer_key")]
