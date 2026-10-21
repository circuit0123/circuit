from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        from core.rls import enable_rls

        post_migrate.connect(enable_rls, dispatch_uid="core.enable_rls")
