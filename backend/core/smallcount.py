"""One rule for every aggregate: a count under DASHBOARD_MIN_COUNT is never shown (it could point at one person)."""

from django.conf import settings


def big_enough(n: int) -> bool:
    return n >= settings.DASHBOARD_MIN_COUNT


def count(n: int) -> dict:
    """A count that is safe to show: below the threshold only the fact that it is small is returned."""
    return {"value": n, "hidden": False} if big_enough(n) else {"value": None, "hidden": True}
