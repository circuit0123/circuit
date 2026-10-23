import pytest

from apps.events import services as events
from apps.events.models import Event
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_many

pytestmark = pytest.mark.django_db


def test_list_newest_first_and_unread_filter(make_member, client_for):
    me = make_member()
    first, second = notify(me, "a"), notify(me, "b")
    c = client_for(me)
    assert [n["id"] for n in c.get("/api/notifications").json()["items"]] == [second.pk, first.pk]
    c.post(f"/api/notifications/{second.pk}/read")
    assert [n["id"] for n in c.get("/api/notifications?unread=true").json()["items"]] == [first.pk]
    assert c.get("/api/notifications/unread-count").json() == {"count": 1}


def test_read_one_is_safe_to_repeat_and_logs_once(make_member, client_for):
    me = make_member()
    n = notify(me, "a")
    c = client_for(me)
    assert c.post(f"/api/notifications/{n.pk}/read").json()["read"] is True
    assert c.post(f"/api/notifications/{n.pk}/read").status_code == 200
    assert Event.objects.filter(type="notification.read", target_id=n.pk).count() == 1


def test_read_all_counts_only_mine(make_member, client_for):
    me, other = make_member(), make_member()
    notify_many([me, me.pk, other], "a")  # duplicates collapse
    notify(me, "b")
    c = client_for(me)
    assert c.post("/api/notifications/read-all").json() == {"count": 2}
    assert c.post("/api/notifications/read-all").json() == {"count": 0}
    assert Notification.objects.get(member=other).read_at is None


def test_someone_elses_notification_is_404(make_member, client_for):
    me, other = make_member(), make_member()
    n = notify(other, "a")
    assert client_for(me).post(f"/api/notifications/{n.pk}/read").status_code == 404
    assert Notification.objects.get(pk=n.pk).read_at is None
    assert client_for(me).get("/api/notifications").json()["items"] == []


def test_unknown_event_type_is_refused():
    with pytest.raises(ValueError, match="Unknown event type"):
        events.record("typo.event")
