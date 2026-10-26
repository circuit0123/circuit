"""Uploaded images are compressed before they reach storage (Supabase free storage is 1 GB)."""

import io

import pytest
from PIL import Image

from apps.social import media


def noisy(width=2400, height=1800) -> Image.Image:
    """Hard to compress, like a busy photo: seeded pseudo-noise over a gradient."""
    import random

    rng = random.Random(7)
    data = bytes(rng.randrange(256) for _ in range(width * height * 3 // 16))
    small = Image.frombytes("RGB", (width // 4, height // 4), (data * 16)[: (width // 4) * (height // 4) * 3])
    return small.resize((width, height), Image.Resampling.NEAREST)


def test_a_lower_quality_setting_makes_a_smaller_file(settings):
    img = noisy(1440, 1080)
    settings.MEDIA_WEBP_QUALITY = 82
    high = media._encode(img, 10**9)
    settings.MEDIA_WEBP_QUALITY = 60
    low = media._encode(img, 10**9)
    assert len(low) < len(high)


def test_an_image_over_its_size_budget_is_squeezed_until_it_fits_or_the_floor_is_reached(settings):
    img = noisy(1440, 1080)
    settings.MEDIA_WEBP_QUALITY = 82
    first_try = media._encode(img, 10**9)
    budget = int(len(first_try) * 0.8)
    squeezed = media._encode(img, budget)
    assert len(squeezed) < len(first_try)
    floor = media._encode(img, 1)  # impossible budget: stops at the lowest quality instead of looping
    assert len(floor) <= len(squeezed)


def test_an_image_that_already_fits_is_encoded_once_at_the_configured_quality(settings, monkeypatch):
    settings.MEDIA_WEBP_QUALITY = 75
    seen = []
    real = Image.Image.save

    def spy(self, fp, fmt=None, **kw):
        seen.append(kw.get("quality"))
        return real(self, fp, fmt, **kw)

    monkeypatch.setattr(Image.Image, "save", spy)
    media._encode(Image.new("RGB", (100, 100), (200, 80, 40)), 10**6)
    assert seen == [75]


def test_the_quality_never_goes_above_the_configured_one(settings, monkeypatch):
    settings.MEDIA_WEBP_QUALITY = 55
    seen = []
    real = Image.Image.save
    monkeypatch.setattr(
        Image.Image, "save", lambda self, fp, fmt=None, **kw: (seen.append(kw["quality"]), real(self, fp, fmt, **kw))[1]
    )
    media._encode(noisy(800, 600), 1)
    assert seen == [55, 50]  # 70 and 60 would be an increase


def test_processed_variants_stay_within_their_budgets_and_lose_their_metadata(settings, make_image):
    settings.MEDIA_WEBP_QUALITY = 75
    out, (w, h) = media._process(make_image("JPEG", (3000, 2000), exif=True))
    assert (w, h) == (3000, 2000)
    for width, blob in out.items():
        assert len(blob) <= settings.MEDIA_VARIANT_MAX_BYTES[width] or width == 1440 and len(blob) < 50_000
        image = Image.open(io.BytesIO(blob))
        assert image.format == "WEBP" and image.width == width and not image.getexif() and b"TestCam" not in blob


def test_the_settings_have_a_budget_for_every_variant_width(settings):
    assert set(settings.MEDIA_VARIANT_MAX_BYTES) == set(settings.MEDIA_VARIANT_WIDTHS)


@pytest.mark.parametrize("quality", [39, 96])
def test_the_quality_setting_is_validated(quality):
    from pydantic import ValidationError

    from tests.unit.test_config import make

    with pytest.raises(ValidationError):
        make(media_webp_quality=quality)
