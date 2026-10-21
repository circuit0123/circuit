from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        from django.conf import settings

        from core.rls import enable_rls

        # Second line of defence behind circuit/config.py: persona tokens must never exist outside dev/demo.
        if settings.DEMO_AUTH and settings.ENV not in ("dev", "demo"):
            raise ImproperlyConfigured("DEMO_AUTH must be off when ENV is staging or production")
        post_migrate.connect(enable_rls, dispatch_uid="core.enable_rls")
