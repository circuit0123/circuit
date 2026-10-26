"""Every screen's calls, in the order its hooks make them, for each scenario the frontend needs to draw.

Personas come from the demo seed (seed/personas.py): Ravi (student), Asha/Priya/Arjun (founders, the circuit), Sneha and Vikram
and Lakshmi (the warm intro), Meenakshi (partner admin). `Call.hook` names the data hook in apps/app/src/data that makes the call;
FRONTEND_HANDOFF.md documents the same screens and a test keeps the two lists in step.
"""

from apps.accounts.models import Member
from tests.contract.runner import Call, Case, World

G, P, PA, PU, D = "GET", "POST", "PATCH", "PUT", "DELETE"


def ravi(w: World) -> Member:
    return w.member("ravi")


def minor(w: World) -> Member:
    return Member.objects.filter(is_minor=True, role="student").order_by("pk").first()  # type: ignore[return-value]


def newbie(w: World) -> Member:
    return w.newbie()


# ids that only exist once the world is seeded
def startup_id(name: str):
    from apps.startups.models import Startup

    return lambda w: Startup.objects.get(name=name).pk


def hiring_startup(w: World) -> int:
    from apps.startups.models import Startup

    return Startup.objects.filter(hiring=True, claimed_by__isnull=False).order_by("pk").first().pk  # type: ignore[union-attr]


def job_id(w: World) -> int:
    from apps.jobs.models import Job

    return Job.objects.filter(is_open=True, startup__claimed_by__isnull=False).order_by("pk").first().pk  # type: ignore[union-attr]


def other_job(w: World) -> int:
    from apps.jobs.models import Job

    return Job.objects.filter(is_open=True, startup__claimed_by__isnull=False).order_by("pk")[1].pk


def story3_job(w: World) -> int:
    from apps.jobs.models import Application

    return Application.objects.order_by("pk").first().job_id  # type: ignore[union-attr]


def applicant_owner(w: World) -> Member:
    from apps.jobs.models import Application
    from apps.startups.services import team_member_ids

    job = Application.objects.select_related("job__startup").order_by("pk").first().job  # type: ignore[union-attr]
    return Member.objects.get(pk=team_member_ids(job.startup)[0])


def first_application(w: World) -> int:
    from apps.jobs.models import Application

    return Application.objects.order_by("pk").first().pk  # type: ignore[union-attr]


def circuit_of(key: str):
    from apps.circuits.models import Circuit

    return lambda w: Circuit.objects.filter(legs__giver=w.member(key)).order_by("pk").first().pk  # type: ignore[union-attr]


def leg_of(key: str):
    from apps.circuits.models import CircuitLeg

    return lambda w: CircuitLeg.objects.filter(giver=w.member(key)).order_by("pk").first().pk  # type: ignore[union-attr]


def received_leg_of(key: str):
    from apps.circuits.models import CircuitLeg

    return lambda w: CircuitLeg.objects.filter(receiver=w.member(key)).order_by("pk").first().pk  # type: ignore[union-attr]


def mid(key: str):
    return lambda w: w.member(key).pk


def first_post(w: World) -> int:
    from apps.social.models import Post

    return Post.objects.filter(visibility="everyone").order_by("pk").first().pk  # type: ignore[union-attr]


def uploaded(purpose: str):
    """A finished upload owned by the calling persona (made the way the browser does: signed URL, file, complete)."""
    import io

    from PIL import Image

    from apps.social import media
    from core.storage import get_storage

    def make(w: World) -> dict:
        owner = w.current  # the persona making this call
        buf = io.BytesIO()
        Image.new("RGB", (320, 320), (40, 120, 90)).save(buf, "PNG")
        upload, _ = media.create_upload(owner, purpose, "image/png", len(buf.getvalue()))
        get_storage().put(media.bucket(purpose), f"{upload.path}/original", buf.getvalue(), "image/png")
        return {"upload_id": media.complete_upload(owner, upload.pk).pk}

    return make


def unclaimed_startup(w: World) -> int:
    from apps.startups.models import Startup

    return Startup.objects.filter(claimed_by__isnull=True, location__isnull=False).order_by("pk").first().pk  # type: ignore[union-attr]


def claim_email(w: World) -> dict:
    from apps.startups.models import Startup

    return {"email": f"founder@{Startup.objects.get(pk=unclaimed_startup(w)).website_domain}"}


def first_wire_key(w: World) -> dict:
    from apps.social.livewire import live_wire

    return {"key": live_wire(w.member("ravi"))[0]["key"]}


def drop_card(w: World) -> int:
    from apps.social.models import DailyDrop

    return DailyDrop.objects.filter(member=w.member("ravi")).order_by("-date").first().candidates[0]["member_id"]  # type: ignore[union-attr]


def chat_of(key: str):
    from django.db.models import Q

    from apps.messaging.models import Conversation

    return lambda w: Conversation.objects.filter(Q(member_a=w.member(key)) | Q(member_b=w.member(key))).order_by("pk").first().pk  # type: ignore[union-attr]


def request_for_divya(w: World) -> int:
    from apps.messaging.models import Conversation

    return Conversation.objects.get(status="request", started_by=w.member("ravi")).pk


def settled(w: World) -> Member:
    return w.newbie(named=True)


def _intro(w: World) -> int:
    from apps.intros.models import IntroRequest

    return IntroRequest.objects.order_by("pk").last().pk  # type: ignore[union-attr]


def _first_notification(w: World, key: str) -> int:
    from apps.notifications.models import Notification

    return Notification.objects.filter(member=w.member(key)).order_by("pk").first().pk  # type: ignore[union-attr]


def _unverified_job(w: World) -> int:
    from apps.jobs.models import Job

    job = Job.objects.filter(startup__claimed_by__isnull=True).order_by("pk").first()
    return job.pk if job else 999999  # no such role is visible to an under-18 either way


def _request_from(key: str):
    from apps.messaging.models import Conversation

    return lambda w: Conversation.objects.get(status="request", started_by=w.member(key), member_b=w.member("ravi")).pk


def _request_to(w: World, key: str) -> int:
    from apps.accounts.models import ConnectionRequest

    return ConnectionRequest.objects.filter(recipient=w.member(key), status="pending").order_by("-pk").first().pk  # type: ignore[union-attr]


def _my_application(w: World, key: str) -> int:
    from apps.jobs.models import Application

    return Application.objects.filter(student=w.member(key)).order_by("-pk").first().pk  # type: ignore[union-attr]


def _latest_job(w: World) -> int:
    from apps.jobs.models import Job

    return Job.objects.order_by("-pk").first().pk  # type: ignore[union-attr]


def _latest_post(w: World) -> int:
    from apps.social.models import Post

    return Post.objects.order_by("-pk").first().pk  # type: ignore[union-attr]


def _latest_reply(w: World) -> int:
    from apps.social.models import Reply

    return Reply.objects.order_by("-pk").first().pk  # type: ignore[union-attr]


def url(fmt: str, *getters):
    """A path built from ids found at run time: url("/api/jobs/{}/apply", job_id)."""
    return lambda w: fmt.format(*[g(w) for g in getters])


CASES: list[Case] = [
    # -- bootstrap: who am I, what is switched on (useFeatures, useMe, useAppearance, useGate) ---------------------------
    Case("bootstrap", "signed_out", None, [Call("useFeatures", G, "/api/config")]),
    Case(
        "bootstrap",
        "default",
        "ravi",
        [
            Call("useFeatures", G, "/api/config"),
            Call("useMe", G, "/api/me"),
            Call("useSettings", G, "/api/me/settings"),
        ],
    ),  # fmt: skip
    Case("bootstrap", "founder", "asha", [Call("useMe", G, "/api/me")]),
    Case("bootstrap", "partner", "meenakshi", [Call("useFeatures", G, "/api/config"), Call("useMe", G, "/api/me")]),
    Case("bootstrap", "under_18", minor, [Call("useFeatures", G, "/api/config"), Call("useMe", G, "/api/me")]),
    Case(
        "bootstrap",
        "features_off",
        "ravi",
        [Call("useFeatures", G, "/api/config")],
        features="pulse:off,daily_drop:off,circuits:off,investor_mode:off,partner_mode:off,promotions:off,payments:off",
    ),
    # -- access: invite code, waitlist, consent (useRedeem, useJoinWaitlist, useConsent, useInviteLink) ------------------------
    Case(
        "access",
        "default",
        "ravi",
        [
            Call("useInviteLink", G, "/api/invites", ignore=("code", "link", "url")),
            Call("useConsent", P, "/api/me/consent", {"policy_version": "2026-01"}),
        ],
    ),  # fmt: skip
    Case(
        "access",
        "beta_gate",
        newbie,
        overrides={"BETA_MODE": True},
        calls=[
            Call("useFeatures", G, "/api/config"),
            Call("useMe", G, "/api/me"),
            Call("useHome", G, "/api/jobs", status=403),
            Call("useRedeem", P, "/api/beta/redeem", {"code": "NOT-A-CODE"}, status=400),
            Call(
                "useJoinWaitlist",
                P,
                "/api/waitlist",
                {
                    "email": "meera@example.org",
                    "role": "student",
                    "city": "Chennai",
                    "college": "SVIT",
                    "note": "",
                    "src": "landing-students",
                },
                status=202,
            ),
        ],
    ),  # fmt: skip
    # -- sign-up: one question per screen (useOnboarding, useCapabilities, useWhere, useOrganisationSearch) -------------------
    Case(
        "signup",
        "new_member",
        newbie,
        [
            Call("useOnboarding", G, "/api/onboarding/state"),
            Call(
                "useOnboarding",
                PA,
                "/api/onboarding/state",
                {"current_step": "name", "answers": {"name": {"display_name": "Meera Rao"}}, "signup_source": "landing-students"},
            ),
            Call("useOnboarding", PA, "/api/me", {"display_name": "Meera Rao", "role": "student"}),
            Call("useWhere", G, "/api/cities"),
            Call("useOnboarding", PA, "/api/me", {"city": "Chennai", "lat": 13.0827, "lng": 80.2707}),
            Call("useOrganisationSearch", G, "/api/organisations/search?q=kav"),
            Call(
                "useOnboarding",
                P,
                "/api/onboarding/extract",
                {"bio": "Third year CSE student. I build web apps and want to learn sales."},
            ),
            Call("useCapabilities", G, "/api/capabilities"),
            Call("useOnboarding", PU, "/api/me/offers", [{"capability": "frontend-dev", "description": ""}]),
            Call("useOnboarding", PU, "/api/me/needs", [{"capability": "performance-marketing", "description": ""}]),
            Call(
                "useOnboarding",
                PU,
                "/api/me/skills",
                [{"capability": "frontend-dev", "level": 2, "proof_url": "https://github.com/meera/shop"}],
            ),
            Call("useOnboarding", PU, "/api/me/traits", ["long-sales-cycle"]),
            Call("useOnboarding", G, "/api/me/offers"),
            Call("useOnboarding", G, "/api/me/needs"),
            Call("useOnboarding", G, "/api/me/skills"),
            Call("useOnboarding", G, "/api/me/traits"),
            Call("useCapabilities", G, "/api/traits"),
            Call("useOnboarding", PU, "/api/me/photo", uploaded("avatar")),
            Call("useOnboarding", D, "/api/me/photo"),
            Call("useOnboarding", PU, "/api/me/photo", uploaded("avatar")),
            Call("useOnboarding", PA, "/api/me/appearance", {"accent": "emerald"}),
            Call("useOnboarding", PA, "/api/onboarding/state", {"completed": True}),
            Call("useDailyDrop", G, "/api/drop/today"),
        ],
    ),  # fmt: skip
    Case(
        "signup",
        "under_18",
        newbie,
        [
            Call("useOnboarding", PA, "/api/onboarding/state", {"answers": {"age": {"adult": False}}, "current_step": "age"}),
            Call("useMe", G, "/api/me"),
            Call("useOnboarding", G, "/api/onboarding/state"),
            Call("useOnboarding", PA, "/api/me/privacy", {"profile_visibility": "public"}, status=403),
        ],
    ),  # fmt: skip
    # -- Home: Live wire, Daily Drop, Pulse (useHome, useLiveWire, useDailyDrop, usePulse, useReact, useRequestIntro) -------------
    Case(
        "home",
        "default",
        "ravi",
        [
            Call("useLiveWire", G, "/api/livewire"),
            Call("useMarkUpdateSeen", P, "/api/livewire/seen", first_wire_key, status=204),
            Call("useDailyDrop", G, "/api/drop/today"),
            Call("useSkip", P, url("/api/drop/today/{}/swipe", drop_card), {"direction": "skip"}),
            Call("usePulse", G, "/api/pulse"),
            Call("useMarkPulseSeen", P, "/api/pulse/seen", status=204),
            Call(
                "useReport",
                P,
                "/api/reports",
                lambda w: {"target_type": "post", "target_id": first_post(w), "reason": "Spam or a scam"},
                status=201,
            ),
            Call("useReact", PU, url("/api/posts/{}/reactions/helpful", first_post), status=204),
            Call("useReact", D, url("/api/posts/{}/reactions/helpful", first_post), status=204),
            Call("useMatches", G, "/api/matches?limit=5"),
        ],
    ),  # fmt: skip
    Case(
        "home",
        "empty",
        settled,
        [
            Call("useLiveWire", G, "/api/livewire"),
            Call("useDailyDrop", G, "/api/drop/today"),
            Call("usePulse", G, "/api/pulse"),
            Call("useMatches", G, "/api/matches"),
            Call("useUnreadCount", G, "/api/notifications/unread-count"),
        ],
    ),  # fmt: skip
    Case(
        "home",
        "founder",
        "asha",
        [
            Call("useLiveWire", G, "/api/livewire"),
            Call("useDailyDrop", G, "/api/drop/today"),
            Call("usePulse", G, "/api/pulse"),
        ],
    ),  # fmt: skip
    Case(
        "home",
        "under_18",
        minor,
        [
            Call("useLiveWire", G, "/api/livewire"),
            Call("useDailyDrop", G, "/api/drop/today"),
            Call("usePulse", G, "/api/pulse"),
            Call("useMatches", G, "/api/matches"),
        ],
    ),  # fmt: skip
    Case(
        "home",
        "features_off",
        "ravi",
        [
            Call("useLiveWire", G, "/api/livewire", status=404),
            Call("useDailyDrop", G, "/api/drop/today", status=404),
            Call("usePulse", G, "/api/pulse", status=404),
            Call("useMatches", G, "/api/matches?limit=5"),
        ],
        features="pulse:off,daily_drop:off,circuits:off,investor_mode:off,partner_mode:off,promotions:off,payments:off",
    ),  # fmt: skip
    # -- Intro requests: the sheet (useIntroPath, useRequestIntro) and the inbox of intros -------------------------------------
    Case(
        "intros",
        "default",
        "sneha",
        [
            Call("useIntroPath", G, url("/api/intros/path/{}", mid("vikram"))),
            Call("useIntroCapacity", G, "/api/intros/capacity"),
            Call(
                "useRequestIntro",
                P,
                "/api/intros",
                lambda w: {"target_id": w.member("vikram").pk, "message": "We are raising a seed round."},
                status=201,
            ),
            Call("useIntroCapacity", G, "/api/intros/capacity"),
            Call("useIntros", G, "/api/intros?box=sent"),
        ],
    ),  # fmt: skip
    Case(
        "intros",
        "broker",
        "lakshmi",
        [
            Call("useIntros", G, "/api/intros?box=brokered"),
            Call("useRespondIntro", P, lambda w: f"/api/intros/{_intro(w)}/respond", {"accept": True}),
        ],
    ),  # fmt: skip
    Case(
        "intros",
        "target",
        "vikram",
        [
            Call("useIntros", G, "/api/intros?box=received"),
            Call("useRespondIntro", P, lambda w: f"/api/intros/{_intro(w)}/respond", {"accept": True}),
        ],
    ),  # fmt: skip
    Case(
        "intros",
        "rating",
        "sneha",
        [
            Call("useRateIntro", P, lambda w: f"/api/intros/{_intro(w)}/rating", {"rating": 5}),
        ],
    ),  # fmt: skip
    Case(
        "intros",
        "under_18",
        minor,
        [
            Call("useIntroCapacity", G, "/api/intros/capacity"),
            Call("useRequestIntro", P, "/api/intros", lambda w: {"target_id": w.member("lakshmi").pk, "message": ""}, status=403),
        ],
    ),  # fmt: skip
    # -- Notifications (useNotifications, useUnreadCount, useMarkRead) ------------------------------------------------------------
    Case(
        "notifications",
        "default",
        "asha",
        [
            Call("useUnreadCount", G, "/api/notifications/unread-count"),
            Call("useNotifications", G, "/api/notifications"),
            Call("useMarkRead", P, lambda w: f"/api/notifications/{_first_notification(w, 'asha')}/read"),
            Call("useMarkRead", P, "/api/notifications/read-all"),
        ],
    ),  # fmt: skip
    Case(
        "notifications",
        "empty",
        settled,
        [
            Call("useUnreadCount", G, "/api/notifications/unread-count"),
            Call("useNotifications", G, "/api/notifications"),
        ],
    ),  # fmt: skip
    # -- Discover: People, Startups, Jobs, Map, search (useDiscover*, useMapPins, useSkillsInDemand) ---------------------------
    Case(
        "discover",
        "people",
        "ravi",
        [
            Call("useDiscoverPeople", G, "/api/matches?limit=40"),
            Call("useDiscoverPeople", G, "/api/matches?role=mentor&verified=true&within_km=25"),
            Call("useDiscoverSearch", G, "/api/search?q=an"),
        ],
    ),  # fmt: skip
    Case(
        "discover",
        "startups",
        "ravi",
        [
            Call("useDiscoverStartups", G, "/api/startups/nearby?limit=40"),
            Call("useMapPins", G, "/api/startups/map?min_lng=80.1&min_lat=12.9&max_lng=80.4&max_lat=13.2"),
            Call("useDiscoverStartups", G, "/api/startups/nearby?hiring=true&limit=10"),
        ],
    ),  # fmt: skip
    Case(
        "discover",
        "jobs",
        "ravi",
        [
            Call("useDiscoverJobs", G, "/api/jobs?limit=50"),
            Call("useSkillsInDemand", G, "/api/jobs/skills-in-demand?within_km=10"),
            Call("useDiscoverJobs", G, "/api/jobs?kind=internship&max_distance_km=10&limit=10"),
        ],
    ),  # fmt: skip
    Case(
        "discover",
        "under_18",
        minor,
        [
            Call("useDiscoverJobs", G, "/api/jobs?limit=50"),
            Call("useSkillsInDemand", G, "/api/jobs/skills-in-demand"),
            Call("useDiscoverStartups", G, "/api/startups/nearby?limit=40"),
            Call("useDiscoverSearch", G, "/api/search?q=an"),
        ],
    ),  # fmt: skip
    Case(
        "discover",
        "empty",
        settled,
        [
            Call("useDiscoverPeople", G, "/api/matches?limit=40"),
            Call("useDiscoverSearch", G, "/api/search?q=zzzz"),
        ],
    ),  # fmt: skip
    # -- Job page and applying (useJob, useApply, useMyApplications) ---------------------------------------------------------------
    Case(
        "job",
        "default",
        "ravi",
        [
            Call("useJob", G, url("/api/jobs/{}", job_id)),
            Call("useApply", P, url("/api/jobs/{}/apply", job_id), status=201),
            Call("useApply", P, url("/api/jobs/{}/apply", job_id), status=200),
            Call("useMyApplications", G, "/api/me/applications"),
        ],
    ),  # fmt: skip
    Case("job", "team", applicant_owner, [Call("useJob", G, url("/api/jobs/{}", story3_job))]),
    Case(
        "job",
        "under_18",
        minor,
        [
            Call("useJob", G, url("/api/jobs/{}", job_id)),
            Call("useApply", P, url("/api/jobs/{}/apply", _unverified_job), status=404),
        ],
    ),  # fmt: skip
    Case(
        "applicants",
        "default",
        applicant_owner,
        [
            Call("useApplicants", G, url("/api/jobs/{}/applicants", story3_job)),
            Call("useSetApplicantStatus", PA, url("/api/applications/{}", first_application), {"status": "shortlisted"}),
        ],
    ),  # fmt: skip
    # -- Startup page (useStartup, useFollows, useFollow, useStartClaim) -------------------------------------------------------------
    Case(
        "startup",
        "default",
        "ravi",
        [
            Call("useStartup", G, url("/api/startups/{}", hiring_startup)),
            Call("useFollow", P, url("/api/startups/{}/follow", hiring_startup), status=204),
            Call("useFollows", G, "/api/me/follows"),
            Call("useStartupJobs", G, url("/api/jobs?startup_id={}", hiring_startup)),
        ],
    ),  # fmt: skip
    Case(
        "startup",
        "claim",
        "asha",
        [
            Call("useStartClaim", P, url("/api/startups/{}/claim", unclaimed_startup), claim_email, ignore=("dev_code",)),
        ],
    ),  # fmt: skip
    Case("startup", "team", "kavya", [Call("useStartup", G, url("/api/startups/{}", startup_id("Vitrix Biosciences")))]),
    Case("startup", "under_18", minor, [Call("useStartup", G, url("/api/startups/{}", hiring_startup))]),
    # -- Circuits (useCircuits, useRespondCircuit, useMarkDone, useRateHandover) ------------------------------------------------------
    Case(
        "circuits",
        "proposed",
        "asha",
        [
            Call("useCircuits", G, "/api/circuits"),
            Call("useCircuits", G, url("/api/circuits/{}", circuit_of("asha"))),
            Call("useRespondCircuit", P, url("/api/circuits/{}/respond", circuit_of("asha")), {"accept": True}),
        ],
    ),  # fmt: skip
    Case(
        "circuits",
        "priya_accepts",
        "priya",
        [Call("useRespondCircuit", P, url("/api/circuits/{}/respond", circuit_of("priya")), {"accept": True})],
    ),
    Case(
        "circuits",
        "active",
        "arjun",
        [
            Call("useRespondCircuit", P, url("/api/circuits/{}/respond", circuit_of("arjun")), {"accept": True}),
            Call("useCircuits", G, "/api/circuits"),
            Call("useMarkDone", P, url("/api/circuits/{}/legs/{}/done", circuit_of("arjun"), leg_of("arjun"))),
        ],
    ),  # fmt: skip
    Case(
        "circuits",
        "rate",
        "priya",
        [
            Call(
                "useRateHandover",
                P,
                url("/api/circuits/{}/legs/{}/rating", circuit_of("priya"), received_leg_of("priya")),
                {"rating": 5},
            ),
            Call("useCircuits", G, "/api/circuits"),
        ],
    ),  # fmt: skip
    Case("circuits", "empty", "ravi", [Call("useCircuits", G, "/api/circuits")]),
    Case(
        "circuits",
        "features_off",
        "asha",
        [Call("useCircuits", G, "/api/circuits", status=404)],
        features="pulse:everyone,daily_drop:everyone,circuits:off,investor_mode:off,partner_mode:off,promotions:off,payments:off",
    ),
    # -- Inbox and Conversation (useInbox, useConnections, useConversation, useStartConversation) --------------------------------
    Case(
        "inbox",
        "default",
        "asha",
        [
            Call("useInbox", G, "/api/conversations?folder=chats"),
            Call("useInbox", G, "/api/conversations?folder=requests"),
            Call("useInboxDot", G, "/api/conversations/unread-count"),
            Call("useConnections", G, "/api/connections"),
        ],
    ),  # fmt: skip
    Case(
        "conversation",
        "default",
        "asha",
        [
            Call("useConversation", G, url("/api/conversations/{}", chat_of("asha"))),
            Call("useConversation", G, url("/api/conversations/{}/messages", chat_of("asha"))),
            Call(
                "useConversation",
                P,
                url("/api/conversations/{}/messages", chat_of("asha")),
                {"body": "Thanks, talk soon."},
                status=201,
            ),
            Call("useConversation", P, url("/api/conversations/{}/read", chat_of("asha"))),
        ],
    ),  # fmt: skip
    Case(
        "conversation",
        "awaiting_reply",
        "ravi",
        [
            Call("useInbox", G, "/api/conversations?folder=requests"),
            Call("useConversation", G, url("/api/conversations/{}", request_for_divya)),
            Call(
                "useConversation",
                P,
                url("/api/conversations/{}/messages", request_for_divya),
                {"body": "Any update?"},
                status=409,
            ),
        ],
    ),  # fmt: skip
    Case(
        "conversation",
        "request",
        "divya",
        [
            Call("useInbox", G, "/api/conversations?folder=requests"),
            Call("useInboxDot", G, "/api/conversations/unread-count"),
            Call("useConversation", G, url("/api/conversations/{}", request_for_divya)),
            Call("useConversation", P, url("/api/conversations/{}/accept", request_for_divya)),
        ],
    ),  # fmt: skip
    Case(
        "conversation",
        "decline",
        "sneha",
        [
            Call(
                "useStartConversation",
                P,
                "/api/conversations",
                lambda w: {"member_id": w.member("ravi").pk, "body": "Hi Ravi, can I ask you something?"},
                status=201,
            ),
        ],
    ),  # fmt: skip
    Case(
        "conversation",
        "decline_answer",
        "ravi",
        [
            Call("useInbox", G, "/api/conversations?folder=requests"),
            Call("useDeclineRequest", P, url("/api/conversations/{}/decline", _request_from("sneha")), status=204),
            Call("useInbox", G, "/api/conversations?folder=requests"),
        ],
    ),  # fmt: skip
    Case(
        "inbox",
        "under_18",
        minor,
        [
            Call("useInbox", G, "/api/conversations?folder=chats"),
            Call("useInboxDot", G, "/api/conversations/unread-count"),
        ],
    ),  # fmt: skip
    Case(
        "inbox",
        "empty",
        settled,
        [
            Call("useInbox", G, "/api/conversations?folder=chats"),
            Call("useInboxDot", G, "/api/conversations/unread-count"),
        ],
    ),  # fmt: skip
    # -- Profile (useProfile) and build logs ---------------------------------------------------------------------------------------
    Case(
        "profile",
        "default",
        "ravi",
        [
            Call("useProfile", G, url("/api/members/{}", mid("lakshmi"))),
            Call("useProfile", G, url("/api/members/{}", mid("ravi"))),
            Call("useProfile", G, url("/api/members/{}/posts", mid("asha"))),
        ],
    ),  # fmt: skip
    Case(
        "profile",
        "hidden_or_blocked",
        "ravi",
        [
            Call("useProfile", G, url("/api/members/{}", mid("admin")), status=404),
            Call("useProfile", G, url("/api/members/{}", lambda w: minor(w).pk), status=404),
        ],
    ),  # fmt: skip
    Case(
        "build_log",
        "default",
        "asha",
        [
            Call("usePost", G, url("/api/posts/{}", first_post)),
            Call("usePostReplies", G, url("/api/posts/{}/replies", first_post)),
            Call("usePostReplies", P, url("/api/posts/{}/replies", first_post), {"body": "Good progress."}, status=201),
            Call("useMemberPosts", G, url("/api/members/{}/posts", mid("asha"))),
            Call(
                "usePostComposer",
                P,
                "/api/posts",
                {"body": "Shipped the first pilot report.", "visibility": "everyone", "capabilities": [], "link": ""},
                status=201,
            ),
            Call(
                "useMediaUpload",
                P,
                "/api/media/uploads",
                {"purpose": "post", "content_type": "image/png", "size": 1000},
                status=201,
                ignore=("upload_url",),
            ),
        ],
    ),  # fmt: skip
    # -- Settings (useSettings, useAppearance, useNotificationPrefs, usePrivacy, useExport, useDeleteAccount) -------------------------
    Case(
        "settings",
        "default",
        "ravi",
        [
            Call("useSettings", G, "/api/me/settings"),
            Call("usePrivacy", PA, "/api/me/privacy", {"read_receipts": True, "visible_to_org": True}),
            Call("useAppearance", PA, "/api/me/appearance", {"theme": "dark", "accent": "mint"}),
            Call("useNotificationPrefs", PA, "/api/me/notification-preferences", {"intros": {"email": False}}),
            Call("useBlocks", G, "/api/me/blocks"),
            Call("useExport", P, "/api/me/export", status=202),
            Call("useSupport", P, "/api/support", {"kind": "question", "message": "How do I change my college?"}, status=202),
            Call("useSupport", G, "/api/support/contact"),
        ],
    ),  # fmt: skip
    Case(
        "settings",
        "under_18",
        minor,
        [
            Call("useSettings", G, "/api/me/settings"),
            Call("usePrivacy", PA, "/api/me/privacy", {"profile_visibility": "public"}, status=403),
            Call("usePrivacy", PA, "/api/me/privacy", {"allow_requests": True}, status=403),
        ],
    ),  # fmt: skip
    # -- Partner dashboard (useDashboard) -------------------------------------------------------------------------------------------
    Case(
        "partner_dashboard",
        "default",
        "meenakshi",
        [
            Call("useDashboard", G, "/api/dashboard/gaps"),
            Call("useDashboard", G, "/api/dashboard/heatmap"),
            Call("useDashboard", G, "/api/dashboard/network"),
            Call("useDashboard", G, "/api/dashboard/acceptance"),
            Call("useOrganisation", G, "/api/organisations/mine"),
            Call("useOrganisation", G, "/api/organisations/mine/members"),
        ],
    ),  # fmt: skip
    Case("partner_dashboard", "not_a_partner", "ravi", [Call("useDashboard", G, "/api/dashboard/gaps", status=403)]),
    # -- Connect, follow, interest, block (useConnect, useFollow, useInterest, useBlocks) ---------------------------------------
    Case(
        "profile",
        "connect_ask",
        "ravi",
        [
            Call(
                "useConnect",
                P,
                "/api/connections/requests",
                lambda w: {"member_id": w.member("arjun").pk, "note": "Loved your hiring board."},
                status=201,
            ),
            Call("useConnectionRequests", G, "/api/connections/requests?box=outgoing"),
        ],
    ),
    Case(
        "profile",
        "connect_answer",
        "arjun",
        [
            Call("useConnectionRequests", G, "/api/connections/requests?box=incoming"),
            Call("useConnect", P, lambda w: f"/api/connections/requests/{_request_to(w, 'arjun')}/respond", {"accept": True}),
            Call("useConnections", G, "/api/connections"),
            Call("useConnect", D, url("/api/connections/{}", mid("ravi")), status=204),
        ],
    ),
    Case(
        "startup",
        "actions",
        "ravi",
        [
            Call("useInterest", P, url("/api/startups/{}/interest", hiring_startup), status=204),
            Call("useInterest", D, url("/api/startups/{}/interest", hiring_startup), status=204),
            Call("useFollow", P, url("/api/startups/{}/follow", hiring_startup), status=204),
            Call("useFollow", D, url("/api/startups/{}/follow", hiring_startup), status=204),
            Call("useApply", P, url("/api/jobs/{}/apply", other_job), status=201),
            Call("useWithdraw", P, lambda w: f"/api/applications/{_my_application(w, 'ravi')}/withdraw"),
        ],
    ),
    Case(
        "job",
        "founder_posts",
        "kavya",
        [
            Call(
                "usePostJob",
                P,
                "/api/jobs",
                lambda w: {
                    "startup_id": startup_id("Vitrix Biosciences")(w),
                    "title": "Lab assistant",
                    "kind": "internship",
                    "description": "Help run assays.",
                    "stipend_min": 8000,
                    "stipend_max": 12000,
                    "location": "Chennai",
                    "duration_weeks": 12,
                    "starts_on": "2026-04-06",
                    "capabilities": [{"capability": "biotech-lab", "required": True}],
                },
            ),
            Call("useEditJob", PA, lambda w: f"/api/jobs/{_latest_job(w)}", {"is_open": False}),
            Call("useEditStartup", PU, url("/api/startups/{}/logo", startup_id("Vitrix Biosciences")), uploaded("startup_logo")),
            Call("useEditStartup", D, url("/api/startups/{}/logo", startup_id("Vitrix Biosciences"))),
            Call(
                "useEditStartup",
                PA,
                url("/api/startups/{}", startup_id("Vitrix Biosciences")),
                {"team_size": 6, "description": "Biotech diagnostics for tier-2 hospitals."},
            ),
        ],
    ),
    Case(
        "settings",
        "blocks",
        "ravi",
        [
            Call("useBlock", P, url("/api/members/{}/block", mid("priya")), status=204),
            Call("useBlocks", G, "/api/me/blocks"),
            Call("useBlock", D, url("/api/members/{}/block", mid("priya")), status=204),
        ],
    ),
    Case(
        "settings",
        "block_from_chat",
        "asha",
        [Call("useBlock", P, url("/api/conversations/{}/block", chat_of("asha")), status=204)],
    ),
    Case(
        "build_log",
        "delete",
        "asha",
        [
            Call(
                "usePostComposer",
                P,
                "/api/posts",
                {"body": "Draft to delete.", "visibility": "everyone", "capabilities": [], "link": ""},
                status=201,
            ),
            Call("useDeletePost", D, lambda w: f"/api/posts/{_latest_post(w)}", status=204),
            Call("useReply", P, url("/api/posts/{}/replies", first_post), {"body": "A reply to remove."}, status=201),
            Call("useDeleteReply", D, lambda w: f"/api/replies/{_latest_reply(w)}", status=204),
        ],
    ),
    # -- Errors: one envelope everywhere ({error: {code, message, details}}) --------------------------------------------------------
    Case(
        "errors",
        "signed_out",
        None,
        [Call("useMe", G, "/api/me", status=401), Call("useSettings", G, "/api/me/settings", status=401)],
    ),
    Case(
        "errors",
        "default",
        "ravi",
        [
            Call("useStartup", G, "/api/startups/999999", status=404),
            Call("useOnboarding", PA, "/api/me", {"not_a_field": 1}, status=422),
            Call("useDiscoverSearch", G, "/api/search?q=a", status=422),
            Call("useApply", P, "/api/jobs/999999/apply", status=404),
            Call("useConversation", P, "/api/conversations/999999/accept", status=404),
        ],
    ),  # fmt: skip
    Case(
        "errors",
        "rate_limited",
        "ravi",
        [
            Call("useOrganisationSearch", G, "/api/organisations/search?q=kav"),
            Call("useOrganisationSearch", G, "/api/organisations/search?q=kav", status=429),
        ],
        overrides={"RATE_LIMITS": {"org_search": (1, 3600)}},
    ),  # fmt: skip
    Case(
        "errors", "beta_required", settled, [Call("useDiscoverJobs", G, "/api/jobs", status=403)], overrides={"BETA_MODE": True}
    ),
]
