from django.contrib import admin

from apps.intros.models import IntroRequest
from core.adminbase import ReadOnlyAdmin

admin.site.register(IntroRequest, ReadOnlyAdmin)
