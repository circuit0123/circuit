from django.contrib import admin

from apps.matching.models import Capability, MatchResult, MemberSkill, MemberTrait, Need, Offer, Trait
from core.adminbase import AuditedAdmin, ReadOnlyAdmin

admin.site.register([Capability, Trait], AuditedAdmin)
admin.site.register([MemberSkill, MemberTrait, Need, Offer, MatchResult], ReadOnlyAdmin)
