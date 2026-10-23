"""The seed's drawn screenshots: every scene renders at 4:5, is repeatable, and the scenes differ from each other."""

import io

import pytest
from PIL import Image

from seed import mockups


@pytest.mark.parametrize("scene", sorted(mockups.SCENES))
def test_scene_renders_a_portrait_png(scene):
    img = Image.open(io.BytesIO(mockups.render(scene)))
    assert img.format == "PNG"
    assert img.size == (1080, 1350)


def test_same_scene_gives_same_bytes():
    assert mockups.render("sync_code") == mockups.render("sync_code")


def test_scenes_are_distinct():
    assert len({mockups.render(s) for s in mockups.SCENES}) == len(mockups.SCENES)
