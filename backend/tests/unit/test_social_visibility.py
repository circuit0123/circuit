"""Who can see a build log. The single-post rule (can_see_post) and the list rule (visible_posts) must always agree."""

import itertools

import pytest

from apps.social.models import Post
from apps.social.relations import can_see_post, visible_posts

pytestmark = pytest.mark.django_db
VIS = ["everyone", "connections", "organisation"]


@pytest.fixture
def world(make_member, make_org, connect, block):
    org, other_org = make_org("KIT"), make_org("Other")
    author = make_member("student", org=org, display_name="Author")
    w = {
        "org": org,
        "author": author,
        "connection": make_member("founder", display_name="Connection"),
        "org_mate": make_member("student", org=org, display_name="Org mate"),
        "stranger": make_member("mentor", display_name="Stranger"),
        "other_org": make_member("student", org=other_org, display_name="Other org"),
        "blocker": make_member("investor", display_name="Blocker"),
        "blocked": make_member("investor", display_name="Blocked"),
    }
    connect(author, w["connection"])
    block(w["blocker"], author)
    block(author, w["blocked"])
    return w


# (viewer, everyone, connections, organisation)
EXPECTED = {
    "author": (True, True, True),
    "connection": (True, True, False),
    "org_mate": (True, False, True),
    "stranger": (True, False, False),
    "other_org": (True, False, False),
    "blocker": (False, False, False),  # blocked the author
    "blocked": (False, False, False),  # blocked by the author
}


@pytest.mark.parametrize("viewer", EXPECTED)
@pytest.mark.parametrize("vis", VIS)
def test_visibility_matrix(world, make_post, viewer, vis):
    post = make_post(world["author"], vis)
    want = EXPECTED[viewer][VIS.index(vis)]
    assert can_see_post(world[viewer], post) is want
    assert (post in visible_posts(world[viewer])) is want  # the list query says the same


def test_connection_who_is_also_org_mate_sees_all(make_member, make_org, connect, make_post):
    org = make_org()
    a, b = make_member("student", org=org), make_member("student", org=org)
    connect(a, b)
    for vis in VIS:
        assert can_see_post(b, make_post(a, vis))


@pytest.mark.parametrize("status", ["hidden", "removed"])
def test_moderated_posts_are_invisible_to_everyone_but_the_author(world, make_post, status):
    post = make_post(world["author"], "everyone", status=status)
    assert can_see_post(world["author"], post)
    for viewer in ("connection", "org_mate", "stranger"):
        assert not can_see_post(world[viewer], post)
        assert post not in visible_posts(world[viewer])


def test_suspended_author_disappears(world, make_post):
    from django.utils import timezone

    post = make_post(world["author"], "everyone")
    world["author"].suspended_at = timezone.now()
    world["author"].save()
    post.refresh_from_db()
    for viewer in ("connection", "org_mate", "stranger"):
        assert not can_see_post(world[viewer], Post.objects.select_related("author").get(pk=post.pk))
        assert post not in visible_posts(world[viewer])


def test_hidden_profile_author_is_only_visible_to_connections_and_org_for_everyone_posts(world, make_post):
    world["author"].profile_visibility = "hidden"
    world["author"].save()
    post = make_post(world["author"], "everyone")
    post = Post.objects.select_related("author").get(pk=post.pk)
    assert can_see_post(world["connection"], post)
    assert not can_see_post(world["stranger"], post)
    assert not can_see_post(world["org_mate"], post)  # a hidden profile's "everyone" post is not org-wide either
    assert post in visible_posts(world["connection"]) and post not in visible_posts(world["stranger"])


def test_minor_author_everyone_post_is_not_public(make_member, make_org, make_post):
    """Defence in depth: the API never lets a minor post publicly, but if such a row existed it still would not leak."""
    org = make_org()
    minor = make_member("student", org=org, is_minor=True)
    stranger = make_member("mentor")
    post = make_post(minor, "everyone")
    assert not can_see_post(stranger, post) and post not in visible_posts(stranger)


def test_list_and_single_rules_agree_everywhere(world, make_post):
    posts = [make_post(world["author"], v) for v in VIS]
    for viewer, post in itertools.product(EXPECTED, posts):
        p = Post.objects.select_related("author").get(pk=post.pk)
        assert can_see_post(world[viewer], p) == (p in visible_posts(world[viewer]))
