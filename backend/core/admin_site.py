"""Admin site: staff login + mandatory TOTP (django-otp). The only place passwords exist."""

from django.conf import settings
from django.template.response import TemplateResponse
from django.urls import path
from django_otp.admin import OTPAdminSite

METRIC_WINDOWS = [{"days": 0, "label": "All time"}, {"days": 7, "label": "7 days"}, {"days": 30, "label": "30 days"}]


class CircuitAdminSite(OTPAdminSite):
    site_header = "Circuit admin"
    site_title = "Circuit admin"

    def has_permission(self, request) -> bool:
        # OTPAdminSite requires a verified TOTP device; also staff-only and super-user-only.
        return super().has_permission(request) and request.user.is_superuser

    def get_urls(self):
        return [path("metrics/", self.admin_view(self.metrics_view), name="metrics"), *super().get_urls()]

    def metrics_view(self, request):
        from apps.beta.funnel import STEPS, funnel

        days = int(request.GET.get("days", 0)) if request.GET.get("days", "0").isdigit() else 0
        rows = [{"src": r["src"], "cells": [r[s] for s in STEPS]} for r in funnel(days or None)]
        context = {
            **self.each_context(request),
            "title": "Metrics",
            "rows": rows,
            "days": days,
            "windows": METRIC_WINDOWS,
            "min_count": settings.DASHBOARD_MIN_COUNT,
        }
        return TemplateResponse(request, "admin/funnel.html", context)
