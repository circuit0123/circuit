from django.contrib import admin, messages

from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
from core.adminbase import ReadOnlyAdmin, audit


@admin.register(CircuitRound)
class CircuitRoundAdmin(ReadOnlyAdmin):
    list_display = ("week", "status", "triggered_by", "started_at", "finished_at")
    actions = ["run_round_now"]

    @admin.action(description="Run circuit round now (current week)")
    def run_round_now(self, request, queryset):
        from apps.circuits.services import run_round

        result = run_round(triggered_by="admin")
        audit(request, "run_circuit_round", queryset.model(pk=0), {"result": result})
        self.message_user(request, f"Round finished: {result}", messages.SUCCESS)


admin.site.register([Circuit, CircuitLeg], ReadOnlyAdmin)
