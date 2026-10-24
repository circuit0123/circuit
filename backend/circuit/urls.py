from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path

from circuit.api import api
from core.errors import api_not_found, handler400, handler403, handler404, handler500  # noqa: F401  (Django looks these up by name)

urlpatterns = [path("api/", api.urls), re_path(r"^api/", api_not_found)]

# Django admin: staff + TOTP only, non-obvious path, never in demo.
if settings.ENV != "demo":
    urlpatterns.append(path(settings.ADMIN_PATH, admin.site.urls))
