"""Admin site: staff login + mandatory TOTP (django-otp). The only place passwords exist."""

from django_otp.admin import OTPAdminSite


class CircuitAdminSite(OTPAdminSite):
    site_header = "Circuit admin"
    site_title = "Circuit admin"

    def has_permission(self, request) -> bool:
        # OTPAdminSite requires a verified TOTP device; also staff-only and super-user-only.
        return super().has_permission(request) and request.user.is_superuser
