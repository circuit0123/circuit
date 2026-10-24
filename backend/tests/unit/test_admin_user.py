import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django_otp.plugins.otp_totp.models import TOTPDevice

pytestmark = pytest.mark.django_db


def test_admin_user_gets_a_password_and_a_totp_device(monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "a-long-enough-pass-1")
    call_command("admin_user", "asha")
    user = get_user_model().objects.get(username="asha")
    assert user.is_staff and user.is_superuser and user.check_password("a-long-enough-pass-1")
    assert TOTPDevice.objects.filter(user=user, confirmed=True).count() == 1
    assert "otpauth://totp/" in capsys.readouterr().out
    call_command("admin_user", "asha")  # again: same user, fresh 2FA device
    assert TOTPDevice.objects.filter(user=user).count() == 1


def test_a_weak_password_is_refused(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "short")
    with pytest.raises(CommandError):
        call_command("admin_user", "bob")
    assert not get_user_model().objects.filter(username="bob").exists()
