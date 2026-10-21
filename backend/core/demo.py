"""DEMO_AUTH persona tokens (dev and demo only).

The switcher in the app lists personas and asks for a token. Every handler 404s unless
DEMO_AUTH is on, and the app refuses to start with DEMO_AUTH in staging/production
(circuit/config.py + core/apps.py), so these endpoints cannot exist in a real environment.
"""

from django.conf import settings
from ninja import Router, Schema

from apps.accounts.models import Member
from core.auth import issue_demo_token
from core.errors import NotFound
from seed.personas import PERSONAS, auth_uuid

router = Router()
PUBLIC_DEMO_BLOCKED = {"admin"}  # the public demo never hands out a super_admin


class Persona(Schema):
    key: str
    role: str
    display_name: str


class PersonaChoice(Schema):
    persona: str


class DemoToken(Schema):
    access_token: str
    expires_in: int


def _available() -> set[str]:
    if not settings.DEMO_AUTH or not (settings.ENV == "dev" or settings.DEMO_PUBLIC):
        raise NotFound()
    keys = set(PERSONAS)
    return keys - PUBLIC_DEMO_BLOCKED if settings.ENV == "demo" else keys


@router.get("/personas", response=list[Persona], auth=None, summary="List demo personas", description="Dev and demo only.")
def personas(request):
    keys = _available()
    return [{"key": k, "role": r, "display_name": n} for k, (r, n) in PERSONAS.items() if k in keys]


@router.post("/token", response=DemoToken, auth=None, summary="Get a demo token", description="Dev and demo only.")
def token(request, body: PersonaChoice):
    if body.persona not in _available():
        raise NotFound("Unknown persona")
    auth_id = auth_uuid(body.persona)
    if not Member.objects.filter(auth_user_id=auth_id).exists():
        raise NotFound("Demo data not loaded; run `make reset-demo`")
    from core.auth import DEMO_TOKEN_TTL

    return {"access_token": issue_demo_token(auth_id), "expires_in": DEMO_TOKEN_TTL}
