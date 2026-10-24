import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = (
        "Create (or reset the 2FA of) a Django admin user for a super admin. Prints the TOTP setup link for an authenticator app."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            password = getpass.getpass("Password (12+ characters): ")
            if password != getpass.getpass("Again: "):
                raise CommandError("Passwords differ")
            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from exc
            user = User(username=username, is_staff=True, is_superuser=True)
            user.set_password(password)
            user.full_clean(exclude=["password"])
            user.save()
        TOTPDevice.objects.filter(user=user).delete()
        device = TOTPDevice.objects.create(user=user, name="authenticator", confirmed=True)
        self.stdout.write(
            f"Admin user '{username}' is ready. Add this to your authenticator app (a link, not a secret to share):"
        )
        self.stdout.write(device.config_url)
