from django.contrib import admin

from apps.notifications.models import Notification
from core.adminbase import ReadOnlyAdmin

admin.site.register(Notification, ReadOnlyAdmin)
