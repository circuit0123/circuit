"""Screenshot-style images of the demo members' (fictional) projects, drawn from simple shapes.

No stock photos and no people (DESIGN.md §5 Imagery and §12). Flat colours only, from Circuit's own palette: no gradients.
Each kind looks like a different kind of project screen. Output is deterministic for the same arguments.
"""

import io
import random

from PIL import Image, ImageDraw, ImageFont

BG, SURFACE, SURFACE_2, BORDER = "#0B0B0E", "#15151A", "#1E1E25", "#2A2A33"
TEXT, MUTED = "#F5F4F0", "#A3A1A8"
ACCENTS = ["#FF5A36", "#7C5CFF", "#2ECC8F", "#FFB020", "#4DA3FF", "#FF4D5E"]
KINDS = ("app", "dashboard", "code", "chart", "board")
SIZE = (1080, 1350)  # 4:5, the portrait build-log shape


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _frame(title: str, subtitle: str, accent: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, SIZE[0] - 60, SIZE[1] - 60), 36, fill=SURFACE, outline=BORDER, width=3)
    d.text((110, 112), title, font=_font(52), fill=TEXT)
    d.text((110, 180), subtitle, font=_font(30), fill=MUTED)
    d.rounded_rectangle((SIZE[0] - 250, 110, SIZE[0] - 110, 160), 25, fill=accent)
    d.line((60, 250, SIZE[0] - 60, 250), fill=BORDER, width=3)
    return img, d


def _app(d: ImageDraw.ImageDraw, rnd: random.Random, accent: str) -> None:
    for i in range(4):
        y = 290 + i * 190
        d.rounded_rectangle((110, y, SIZE[0] - 110, y + 160), 24, fill=SURFACE_2)
        d.ellipse((140, y + 35, 230, y + 125), fill=ACCENTS[(i + rnd.randrange(3)) % len(ACCENTS)])
        d.rounded_rectangle((260, y + 38, 260 + rnd.randint(300, 560), y + 66), 12, fill=TEXT)
        d.rounded_rectangle((260, y + 92, 260 + rnd.randint(200, 420), y + 114), 10, fill=MUTED)
    d.rounded_rectangle((110, 1100, SIZE[0] - 110, 1190), 30, fill=accent)


def _dashboard(d: ImageDraw.ImageDraw, rnd: random.Random, accent: str) -> None:
    for i in range(3):
        x = 110 + i * 285
        d.rounded_rectangle((x, 290, x + 255, 450), 22, fill=SURFACE_2)
        d.text((x + 24, 312), ["Samples", "On time", "Open"][i], font=_font(26), fill=MUTED)
        d.text((x + 24, 360), str(rnd.randint(12, 980)), font=_font(60), fill=TEXT)
    d.rounded_rectangle((110, 490, SIZE[0] - 110, 1230), 28, fill=SURFACE_2)
    base = 1160
    for i in range(10):
        h = rnd.randint(120, 560)
        x = 160 + i * 78
        d.rounded_rectangle((x, base - h, x + 58, base), 10, fill=accent if i % 3 == 0 else BORDER)
    d.line((150, base + 10, SIZE[0] - 150, base + 10), fill=MUTED, width=3)


def _code(d: ImageDraw.ImageDraw, rnd: random.Random, accent: str) -> None:
    d.rounded_rectangle((110, 290, SIZE[0] - 110, 1230), 24, fill="#0F0F14")
    y = 330
    for i in range(18):
        indent = rnd.choice([0, 0, 40, 80])
        d.text((140, y), f"{i + 1:>2}", font=_font(28), fill=BORDER)
        x = 210 + indent
        for _ in range(rnd.randint(2, 4)):
            w = rnd.randint(60, 220)
            if x + w > SIZE[0] - 140:
                break
            d.rounded_rectangle((x, y + 6, x + w, y + 28), 8, fill=rnd.choice([accent, MUTED, "#4DA3FF", "#2ECC8F"]))
            x += w + 18
        y += 50


def _chart(d: ImageDraw.ImageDraw, rnd: random.Random, accent: str) -> None:
    d.rounded_rectangle((110, 290, SIZE[0] - 110, 1230), 28, fill=SURFACE_2)
    for i in range(6):
        y = 380 + i * 140
        d.line((160, y, SIZE[0] - 160, y), fill=BORDER, width=2)
    pts, v = [], 800
    for i in range(9):
        v = max(420, min(1120, v + rnd.randint(-160, 120)))
        pts.append((160 + i * 108, v))
    d.line(pts, fill=accent, width=10, joint="curve")
    for p in pts:
        d.ellipse((p[0] - 16, p[1] - 16, p[0] + 16, p[1] + 16), fill=TEXT, outline=accent, width=6)


def _board(d: ImageDraw.ImageDraw, rnd: random.Random, accent: str) -> None:
    for c in range(3):
        x = 110 + c * 285
        d.text((x, 285), ["To do", "Doing", "Done"][c], font=_font(30), fill=MUTED)
        for r in range(rnd.randint(2, 4)):
            y = 340 + r * 220
            d.rounded_rectangle((x, y, x + 255, y + 190), 20, fill=SURFACE_2)
            d.rounded_rectangle((x + 20, y + 24, x + 20 + rnd.randint(120, 200), y + 46), 10, fill=TEXT)
            d.rounded_rectangle((x + 20, y + 70, x + 20 + rnd.randint(80, 190), y + 90), 9, fill=MUTED)
            d.rounded_rectangle((x + 20, y + 140, x + 100, y + 164), 12, fill=accent if c == 2 else BORDER)


_DRAW = {"app": _app, "dashboard": _dashboard, "code": _code, "chart": _chart, "board": _board}


def render(kind: str, title: str, subtitle: str, seed: int) -> bytes:
    """A PNG (4:5) that looks like a screenshot of `title`. Same arguments, same bytes."""
    rnd = random.Random(f"{kind}:{title}:{seed}")
    accent = ACCENTS[seed % len(ACCENTS)]
    img, d = _frame(title, subtitle, accent)
    _DRAW[kind](d, rnd, accent)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
