from django.core.management.base import BaseCommand
from django.utils import timezone

from core import jobhealth


class Command(BaseCommand):
    help = "Print every scheduled job's last result and whether it is overdue (no success for twice its interval). Read-only."

    def handle(self, *args, **options):
        rows = jobhealth.status()
        if not rows:
            self.stdout.write(
                "No scheduled jobs are expected here: JOB_INTERVALS is empty (it is set by the deploy script in the cloud)."
            )
            return
        now = timezone.now()

        def ago(when):
            if when is None:
                return "never"
            minutes = int((now - when).total_seconds() // 60)
            return (
                f"{minutes}m ago" if minutes < 120 else f"{minutes // 60}h ago" if minutes < 2880 else f"{minutes // 1440}d ago"
            )

        self.stdout.write(f"{'JOB':<24} {'EVERY':>6} {'LAST RESULT':<11} {'LAST SUCCESS':<13} STATE")
        for r in rows:
            state = "OVERDUE: " + r.reason if r.overdue else (r.reason or "ok")
            self.stdout.write(
                f"{r.name:<24} {str(r.interval_minutes) + 'm':>6} {r.last_status or '-':<11} {ago(r.last_success_at):<13} {state}"
            )
            if r.last_error:
                self.stdout.write(f"{'':<24} last error: {r.last_error}")
        late = sum(1 for r in rows if r.overdue)
        self.stdout.write(f"\n{late} overdue of {len(rows)}.")
