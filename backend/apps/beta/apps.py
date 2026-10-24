from django.apps import AppConfig


class BetaConfig(AppConfig):
    name = "apps.beta"

    def ready(self) -> None:
        from corsheaders.signals import check_request_enabled

        from apps.beta.cors import allow_landing_for_waitlist

        check_request_enabled.connect(allow_landing_for_waitlist, dispatch_uid="beta.cors_waitlist")
