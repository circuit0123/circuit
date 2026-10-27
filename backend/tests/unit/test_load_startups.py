import csv

import httpx
import pytest
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command

from apps.accounts.models import Member
from apps.events.models import Event
from apps.startups import geocode
from apps.startups.admin import StartupForm
from apps.startups.load import REQUIRED
from apps.startups.management.commands.load_startups import Command
from apps.startups.models import Startup

pytestmark = pytest.mark.django_db
COLUMNS = [*REQUIRED, "careers_url", "funding_evidence", "address_source", "needs_check", "scraped_from", "scraped_at"]
CHENNAI = (13.05, 80.25)


class FakeGeo:
    def __init__(self, answers=None):
        self.answers, self.calls = answers or {}, []

    def lookup(self, address):
        self.calls.append(address)
        return self.answers.get(address)


def row(name, domain, **kw):
    base = dict.fromkeys(COLUMNS, "")
    base.update(name=name, website_domain=domain, city="Chennai", description="d", sector="fintech", stage="seed", hiring="true",
                confidence="high", careers_url="https://x.test/jobs")  # fmt: skip
    return base | kw


def write(tmp_path, rows):
    p = tmp_path / "s.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return p


def run(path, geo, *extra):
    Command.geocoder = geo
    try:
        call_command("load_startups", str(path), *extra)
    finally:
        Command.geocoder = None


def test_creates_unclaimed_visible_crawler_startups_with_one_event_each(tmp_path):
    geo = FakeGeo({"1 Main Rd, Chennai": CHENNAI})
    run(write(tmp_path, [row("A", "a.com", address="1 Main Rd, Chennai"), row("B", "b.com", sector="ai")]), geo)
    a, b = Startup.objects.get(website_domain="a.com"), Startup.objects.get(website_domain="b.com")
    assert a.source == "crawler" and a.claimed_by is None and a.hidden_at is None
    assert (a.location.y, a.location.x) == CHENNAI and a.details["careers_url"] == "https://x.test/jobs"
    assert b.location is None and b.sector == "deeptech"
    events = Event.objects.filter(type="startup.created")
    assert events.count() == 2 and set(events[0].payload) == {"sector", "city", "has_pin"}


def test_running_again_changes_nothing_and_does_not_geocode_again(tmp_path):
    path = write(tmp_path, [row("A", "a.com", address="1 Main Rd, Chennai")])
    run(path, FakeGeo({"1 Main Rd, Chennai": CHENNAI}))
    before = list(Startup.objects.values())
    run(path, FakeGeo({"1 Main Rd, Chennai": CHENNAI}))
    assert list(Startup.objects.values()) == before and Event.objects.filter(type="startup.created").count() == 1


def test_claimed_startup_is_untouched(tmp_path):
    m = Member.objects.create(auth_user_id="00000000-0000-0000-0000-000000000001", role="founder", display_name="F")
    s = Startup.objects.create(name="Mine", website_domain="a.com", source="crawler", claimed_by=m, description="mine")
    run(write(tmp_path, [row("A", "a.com", address="1 Main Rd, Chennai")]), FakeGeo({"1 Main Rd, Chennai": CHENNAI}))
    s.refresh_from_db()
    assert (s.name, s.description, s.location, s.address) == ("Mine", "mine", None, "")


def test_dry_run_writes_nothing_and_reports(tmp_path, capsys):
    run(write(tmp_path, [row("A", "a.com", address="1 Main Rd, Chennai"), row("B", "b.com", address="Nowhere")]),
        FakeGeo({"1 Main Rd, Chennai": CHENNAI}), "--dry-run")  # fmt: skip
    out = capsys.readouterr().out
    assert not Startup.objects.exists() and not Event.objects.filter(type="startup.created").exists()
    assert "DRY RUN" in out and "created 2" in out and "hits 1, misses 1" in out


def test_no_address_area_only_and_far_hits_get_no_pin_and_no_lookup(tmp_path):
    geo = FakeGeo({"Far St": (28.6, 77.2), "Guindy": CHENNAI})
    run(
        write(
            tmp_path,
            [
                row("A", "a.com"),
                row("B", "b.com", address="Guindy", address_note="area only"),
                row("C", "c.com", address="Far St"),
            ],
        ),
        geo,
    )
    assert geo.calls == ["Far St"]
    assert Startup.objects.filter(location__isnull=False).count() == 0
    assert Startup.objects.get(website_domain="b.com").address == "Guindy"


def test_unknown_sector_maps_to_closest_and_is_reported(tmp_path, capsys):
    run(write(tmp_path, [row("A", "a.com", sector="fintek")]), FakeGeo())
    assert Startup.objects.get().sector == "fintech" and "WARNING: unknown sector 'fintek'" in capsys.readouterr().out


def test_a_pin_fixed_in_admin_survives_a_rerun(tmp_path):
    path = write(tmp_path, [row("A", "a.com", address="1 Main Rd, Chennai")])
    run(path, FakeGeo())
    Startup.objects.update(location=Point(80.3, 13.1, srid=4326), address="Fixed address")
    run(path, FakeGeo({"1 Main Rd, Chennai": CHENNAI}))
    s = Startup.objects.get()
    assert s.address == "Fixed address" and s.location.x == 80.3


def test_missing_column_and_missing_file_fail_clearly(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name\nA\n")
    with pytest.raises(CommandError, match="missing columns"):
        run(bad, FakeGeo())
    with pytest.raises(CommandError, match="No such file"):
        run(tmp_path / "nope.csv", FakeGeo())


def test_admin_form_pin_fields():
    s = Startup.objects.create(name="A", website_domain="a.com")
    base = {
        "name": "A",
        "website_domain": "a.com",
        "source": "crawler",
        "confidence": 1,
        "details": "{}",
        "view_count": 0,
        "tech_stack": "[]",
    }
    f = StartupForm({**base, "latitude": "13.1", "longitude": "80.2"}, instance=s)
    assert f.is_valid(), f.errors
    f.save()
    assert (s.location.y, s.location.x) == (13.1, 80.2)
    assert not StartupForm({**base, "latitude": "13.1"}, instance=s).is_valid()
    f = StartupForm({**base}, instance=s)
    assert f.is_valid() and f.save().location is None


def test_geocoder_retries_then_gives_up_and_caches_only_answers(tmp_path, monkeypatch, settings):
    settings.SUPPORT_EMAIL = "ops@circuit.test"
    calls = []

    def fake_get(url, **kw):
        calls.append(kw["headers"]["User-Agent"])
        if len(calls) < 3:
            return httpx.Response(429, request=httpx.Request("GET", url))
        return httpx.Response(200, json=[{"lat": "13.0", "lon": "80.2"}], request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(geocode.time, "sleep", lambda s: None)
    g = geocode.Nominatim(tmp_path / "c.json", pause=0)
    assert g.lookup("x") == (13.0, 80.2) and "ops@circuit.test" in calls[0]
    assert geocode.Nominatim(tmp_path / "c.json").lookup("x") == (13.0, 80.2)  # from the file, no request
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectTimeout("t")))
    g2 = geocode.Nominatim(tmp_path / "d.json", pause=0)
    assert g2.lookup("y") is None and g2.stats["errors"] == 1 and "y" not in g2.cache


def test_geocoder_refuses_a_placeholder_support_email(settings, tmp_path):
    settings.SUPPORT_EMAIL = "support@example.com"
    with pytest.raises(ValueError, match="SUPPORT_EMAIL"):
        geocode.Nominatim(tmp_path / "c.json")
