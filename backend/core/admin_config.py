from django.contrib.admin.apps import AdminConfig


class CircuitAdminConfig(AdminConfig):
    # Dotted path, imported lazily, so django_otp's models are ready by then.
    default_site = "core.admin_site.CircuitAdminSite"
