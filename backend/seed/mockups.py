"""Believable screens for the demo build logs, drawn with Pillow.

DESIGN.md §5 Imagery: build-log images must look like real work (readable text, concrete data) and never use grey
placeholder bars. Each scene is one specific screen: an attendance app, a lab dashboard, an investor update, code.
No stock photos, no people, no gradients. Output is deterministic: the same scene gives the same bytes.

Only Pillow's bundled font is used (it has no ₹ or Indian scripts), so the rupee sign is drawn by `rupee` and text
stays in Latin script. Code is set in a fixed pitch by placing each character, since no monospace font is bundled.
"""

import io
import re
import textwrap
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350  # 4:5, the portrait build-log shape
Draw = ImageDraw.ImageDraw

DARK = {"bg": "#0F1115", "card": "#171A21", "line": "#262B36", "text": "#E8EAF0", "muted": "#8B93A3"}
LIGHT = {"bg": "#F5F6F8", "card": "#FFFFFF", "line": "#E3E6EB", "text": "#14171F", "muted": "#6B7280"}
GREEN, RED, AMBER, BLUE, VIOLET = "#34C38F", "#F0616D", "#F5B544", "#4C8DFF", "#8B7CFF"
GREEN_L, RED_L, AMBER_L, BLUE_L = "#14A36B", "#D92D3E", "#C98200", "#2563EB"

_fonts: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def font(size: int):
    if size not in _fonts:
        _fonts[size] = ImageFont.load_default(size=size)
    return _fonts[size]


def text(d: Draw, xy, s: str, size: int, fill: str, bold: bool = False, anchor: str = "la") -> float:
    """Draw text and return its right edge. `bold` thickens the stroke, since only one weight is bundled."""
    f = font(size)
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=1 if bold and size >= 30 else 0, stroke_fill=fill)
    return xy[0] + d.textlength(s, font=f)


def width(d: Draw, s: str, size: int) -> float:
    return d.textlength(s, font=font(size))


def rr(d: Draw, box, r: int = 20, fill=None, outline=None, w: int = 2) -> None:
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


def pill(d: Draw, x: float, y: float, s: str, size: int, bg: str, fg: str, pad: int = 16, right: bool = False) -> float:
    w = width(d, s, size) + pad * 2
    if right:
        x -= w
    rr(d, (x, y, x + w, y + size + 16), (size + 16) // 2, fill=bg)
    text(d, (x + pad, y + 7), s, size, fg)
    return x + w


def rupee(d: Draw, x: float, base: float, size: int, fill: str) -> float:
    """A drawn ₹ (the bundled font lacks it). `base` is the text baseline; returns the advance."""
    h, w, s = 0.7 * size, 0.5 * size, max(2, size // 11)
    top = base - h
    r = 0.27 * h
    cx = x + w * 0.5
    d.line((x, top, cx, top), fill=fill, width=s)
    d.line((x, top + 2 * r, cx, top + 2 * r), fill=fill, width=s)
    d.arc((cx - r, top, cx + r, top + 2 * r), -90, 90, fill=fill, width=s)
    d.line((x - 1, top + 0.3 * h, x + w + 1, top + 0.3 * h), fill=fill, width=s)  # the bar through the bowl
    d.line((x + w * 0.08, top + 2 * r, x + w * 0.95, base), fill=fill, width=s)
    d.line((x - 1, top, x + w + 1, top), fill=fill, width=s)
    return w + 0.14 * size


def money(d: Draw, x: float, base: float, s: str, size: int, fill: str, bold: bool = False, right: bool = False) -> float:
    """`₹` followed by `s`, left aligned at x or right aligned to x. Returns the far edge."""
    total = 0.5 * size + 0.14 * size + width(d, s, size)
    if right:
        x -= total
    adv = rupee(d, x, base, size, fill)
    return text(d, (x + adv, base), s, size, fill, bold, "ls")


def mono(d: Draw, x: float, y: float, s: str, size: int, fill: str) -> float:
    """Fixed pitch: every character in its own cell."""
    pitch = size * 0.58
    for i, ch in enumerate(s):
        if ch != " ":
            d.text((x + (i + 0.5) * pitch, y), ch, font=font(size), fill=fill, anchor="ma")
    return x + len(s) * pitch


def wrap(d: Draw, s: str, size: int, max_w: int) -> list[str]:
    chars = max(10, int(max_w / (width(d, "n", size) * 1.02)))
    return textwrap.wrap(s, chars)


def canvas(theme: dict) -> tuple[Image.Image, Draw]:
    img = Image.new("RGB", (W, H), theme["bg"])
    return img, ImageDraw.Draw(img)


def status_bar(d: Draw, t: dict) -> None:
    text(d, (64, 36), "9:41", 32, t["text"], True)
    for i in range(4):
        d.rectangle((W - 230 + i * 14, 62 - 8 - i * 6, W - 230 + i * 14 + 9, 62), fill=t["text"])
    rr(d, (W - 150, 38, W - 74, 66), 8, outline=t["text"], w=2)
    d.rectangle((W - 144, 44, W - 98, 60), fill=t["text"])


def tick(d: Draw, cx: float, cy: float, r: float, fill: str, fg: str) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    d.line(
        (cx - r * 0.42, cy + r * 0.02, cx - r * 0.1, cy + r * 0.38, cx + r * 0.46, cy - r * 0.36),
        fill=fg,
        width=max(3, int(r / 5)),
        joint="curve",
    )


# -- charts ---------------------------------------------------------------------------------------------------
def line_chart(d, box, series, ymax, yticks, xlabels, t, fmt=str, dashed_at=None, label_size=24):
    x0, y0, x1, y1 = box
    n = len(xlabels)
    for v in yticks:
        y = y1 - (y1 - y0) * v / ymax
        d.line((x0, y, x1, y), fill=t["line"], width=2)
        text(d, (x0 - 14, y), fmt(v), label_size, t["muted"], anchor="rm")
    xs = [x0 + 30 + (x1 - x0 - 60) * i / (n - 1) for i in range(n)]
    for x, lab in zip(xs, xlabels):
        text(d, (x, y1 + 16), lab, label_size, t["muted"], anchor="ma")
    out = []
    for vals, colour, wd in series:
        pts = [(x, y1 - (y1 - y0) * v / ymax) for x, v in zip(xs, vals)]
        d.line(pts, fill=colour, width=wd, joint="curve")
        for p in pts:
            d.ellipse((p[0] - wd - 1, p[1] - wd - 1, p[0] + wd + 1, p[1] + wd + 1), fill=t["card"], outline=colour, width=3)
        out.append(pts)
    return out


# -- scenes ---------------------------------------------------------------------------------------------------
def turnaround_tracker() -> Image.Image:
    t = DARK
    img, d = canvas(t)
    text(d, (60, 64), "Turnaround tracker", 56, t["text"], True)
    text(d, (60, 138), "Week 6  ·  14 labs  ·  Coimbatore region", 28, t["muted"])
    pill(d, W - 60, 74, "Live", 26, "#12342A", GREEN, right=True)
    tiles = [
        ("Samples this week", "1,284", "+8% on week 5", GREEN),
        ("Delivered on time", "91.4%", "SLA is 6 hours", t["muted"]),
        ("Flagged late", "37", "9 at Vasan Path Lab", RED),
    ]
    for i, (lab, val, sub, col) in enumerate(tiles):
        x = 60 + i * 328
        rr(d, (x, 206, x + 304, 396), 22, fill=t["card"], outline=t["line"])
        text(d, (x + 24, 228), lab, 24, t["muted"])
        text(d, (x + 24, 270), val, 68, t["text"], True)
        text(d, (x + 24, 354), sub, 23, col)
    rr(d, (60, 424, W - 60, 862), 24, fill=t["card"], outline=t["line"])
    text(d, (92, 450), "Average turnaround by day (hours)", 30, t["text"], True)
    days, vals = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], [5.1, 5.6, 6.4, 5.8, 7.1, 4.9, 4.4]
    cx0, cx1, cy0, cy1 = 140, W - 100, 530, 790
    for g in (0, 3, 6, 9):
        y = cy1 - (cy1 - cy0) * g / 9
        d.line((cx0, y, cx1, y), fill=t["line"], width=2)
        text(d, (cx0 - 14, y), str(g), 24, t["muted"], anchor="rm")
    slot = (cx1 - cx0) / 7
    for i, (day, v) in enumerate(zip(days, vals)):
        bx = cx0 + i * slot + slot * 0.2
        top = cy1 - (cy1 - cy0) * v / 9
        rr(d, (bx, top, bx + slot * 0.6, cy1), 8, fill=RED if v > 6 else BLUE)
        text(d, (bx + slot * 0.3, top + 14), f"{v:.1f}", 24, "#FFFFFF", True, "ma")
        text(d, (bx + slot * 0.3, cy1 + 14), day, 24, t["muted"], anchor="ma")
    y6 = cy1 - (cy1 - cy0) * 6 / 9
    for x in range(cx0, cx1, 26):
        d.line((x, y6, x + 14, y6), fill=AMBER, width=3)
    text(d, (cx1, y6 - 34), "SLA 6 h", 24, AMBER, anchor="ra")
    rr(d, (60, 890, W - 60, 1296), 24, fill=t["card"], outline=t["line"])
    heads = [("Lab", 92, "la"), ("Samples", 600, "ra"), ("Avg TAT", 770, "ra"), ("Late", W - 92, "ra")]
    for lab, x, a in heads:
        text(d, (x, 918), lab, 24, t["muted"], anchor=a)
    rows = [
        ("Sankara Diagnostics", 212, "5.2 h", 4),
        ("Vasan Path Lab", 188, "6.8 h", 9),
        ("Lakshmi Labs, Salem", 164, "4.9 h", 2),
        ("KMCH Central Lab", 301, "7.4 h", 14),
        ("Aravind Pathology", 219, "5.6 h", 5),
    ]
    for i, (lab, n, tat, late) in enumerate(rows):
        y = 964 + i * 64
        d.line((92, y - 8, W - 92, y - 8), fill=t["line"], width=2)
        text(d, (92, y + 4), lab, 28, t["text"])
        text(d, (600, y + 4), str(n), 28, t["text"], anchor="ra")
        text(d, (770, y + 4), tat, 28, RED if float(tat.split()[0]) > 6 else t["text"], anchor="ra")
        if late > 8:
            pill(d, W - 92, y - 2, f"{late} flagged", 24, "#3A1A1F", RED, right=True)
        else:
            text(d, (W - 92, y + 4), str(late), 28, t["text"], anchor="ra")
    return img


def investor_update() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    rr(d, (60, 60, W - 60, H - 60), 28, fill=t["card"], outline=t["line"])
    text(d, (110, 110), "Medha Health", 28, t["muted"])
    text(d, (110, 156), "Investor update, September", 52, t["text"], True)
    stats = [
        ("MRR", None, "4.8L", "+18% on August"),
        ("Runway", "14", "months", "at current spend"),
        ("Hospitals live", "11", "", "+2 this month"),
    ]
    for i, (lab, big, unit, sub) in enumerate(stats):
        x = 110 + i * 300
        text(d, (x, 250), lab, 24, t["muted"])
        if big is None:
            end = money(d, x, 340, unit, 62, t["text"], True)
        else:
            end = text(d, (x, 286), big, 62, t["text"], True)
            text(d, (end + 10, 322), unit, 28, t["text"]) if unit else None
        text(d, (x, 364), sub, 23, GREEN_L)
    text(d, (110, 450), "Monthly recurring revenue (₹ lakh)".replace("₹ ", "Rs "), 26, t["muted"])
    box = (200, 520, W - 130, 940)
    mrr = [1.9, 2.4, 2.9, 3.4, 4.1, 4.8]
    pts = line_chart(
        d, box, [(mrr, BLUE_L, 6)], 6, [0, 2, 4, 6], ["Apr", "May", "Jun", "Jul", "Aug", "Sep"], t, fmt=lambda v: f"{v}L"
    )
    px, py = pts[0][-1]
    d.ellipse((px - 16, py - 16, px + 16, py + 16), fill=BLUE_L)
    rr(d, (px - 150, py - 92, px - 10, py - 36), 14, fill=t["text"])
    money(d, px - 134, py - 52, "4.8L", 32, t["card"], True)
    rr(d, (110, 1050, W - 110, 1250), 20, fill="#F1F5FF")
    d.rectangle((110, 1050, 120, 1250), fill=BLUE_L)
    text(d, (150, 1076), "The ask", 24, BLUE_L, True)
    text(d, (150, 1116), "Two intros to hospital CFOs in Chennai.", 32, t["text"], True)
    text(d, (150, 1170), "Reply and I will send the one-page pitch.", 28, t["muted"])
    return img


def hiring_board() -> Image.Image:
    t = DARK
    img, d = canvas(t)
    text(d, (60, 64), "Hiring: Backend engineer", 52, t["text"], True)
    text(d, (60, 134), "Two-day trial projects  ·  9 candidates", 28, t["muted"])
    cols = [
        (
            "Trial sent",
            [
                ("Harini S.", "Fix the checkout rounding bug", "Starts Mon", t["muted"]),
                ("Mohammed Rafi", "Add retries to the SMS sender", "Starts Mon", t["muted"]),
                ("Deepak Nair", "Fix the checkout rounding bug", "Starts Tue", t["muted"]),
            ],
        ),
        (
            "In progress",
            [
                ("Sowmya K.", "Add retries to the SMS sender", "Day 2 of 2", AMBER),
                ("Tarun Jain", "Speed up the invoice query", "Day 1 of 2", BLUE),
                ("Ishita Bose", "Speed up the invoice query", "Day 1 of 2", BLUE),
            ],
        ),
        (
            "Reviewed",
            [
                ("Vignesh R.", "Fix the checkout rounding bug", "Offer sent", GREEN),
                ("Pooja Menon", "Add retries to the SMS sender", "Strong, 2nd round", GREEN),
                ("Anand Kumar", "Speed up the invoice query", "Not this time", t["muted"]),
            ],
        ),
    ]
    cw = 304
    for c, (title, cards) in enumerate(cols):
        x = 60 + c * (cw + 24)
        text(d, (x, 222), title, 28, t["text"], True)
        text(d, (x + cw, 226), str(len(cards)), 26, t["muted"], anchor="ra")
        for r, (name, task, tag, col) in enumerate(cards):
            y = 280 + r * 330
            rr(d, (x, y, x + cw, y + 300), 22, fill=t["card"], outline=t["line"])
            text(d, (x + 22, y + 24), name, 30, t["text"], True)
            for k, line in enumerate(wrap(d, task, 25, cw - 44)[:3]):
                text(d, (x + 22, y + 76 + k * 34), line, 25, t["muted"])
            d.ellipse((x + 22, y + 238, x + 38, y + 254), fill=col)
            text(d, (x + 50, y + 232), tag, 24, col if col != t["muted"] else t["muted"])
    return img


def assay_run() -> Image.Image:
    t = DARK
    img, d = canvas(t)
    text(d, (60, 64), "Assay run 14", 56, t["text"], True)
    text(d, (60, 138), "Plate reader  ·  96-well  ·  ex 485 / em 520 nm  ·  gain 80", 26, t["muted"])
    rr(d, (60, 200, W - 60, 960), 24, fill=t["card"], outline=t["line"])
    text(d, (92, 228), "Fluorescence over time (RFU)", 30, t["text"], True)
    sample = [900, 2600, 4300, 5900, 7000, 8300, 8900, 9300, 9400]
    blank = [880, 890, 900, 910, 905, 900, 915, 900, 905]
    pts = line_chart(
        d,
        (210, 330, W - 120, 840),
        [(sample, GREEN, 6), (blank, t["muted"], 4)],
        10000,
        [0, 2500, 5000, 7500, 10000],
        ["0", "5", "10", "15", "20", "30", "40", "50", "60"],
        t,
        fmt=lambda v: f"{v:,}",
    )
    text(d, (W / 2 + 40, 906), "minutes", 24, t["muted"], anchor="ma")
    sx, sy = pts[0][-1]
    text(d, (sx - 24, sy + 34), "Sample", 26, GREEN, True, "ra")
    bx, by = pts[1][-1]
    text(d, (bx - 24, by - 50), "Blank", 26, t["muted"], True, "ra")
    for i, (lab, val, col) in enumerate(
        [
            ("Signal to noise", "10.4", GREEN),
            ("Mean sample", "9,412", t["text"]),
            ("Mean blank", "905", t["text"]),
            ("CV", "3.1%", t["text"]),
        ]
    ):
        x, w = 60 + i * 245, 225
        rr(d, (x, 990, x + w, 1170), 20, fill=t["card"], outline=t["line"])
        text(d, (x + 20, 1010), lab, 22, t["muted"])
        text(d, (x + 20, 1060), val, 52 if i == 0 else 44, col, True)
    text(d, (60, 1210), "Settings kept: gain 80, 37 C, read every 5 minutes after 20.", 25, t["muted"])
    return img


def onboarding_phone() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    status_bar(d, t)
    text(d, (64, 130), "Set up your studio", 58, t["text"], True)
    text(d, (64, 208), "2 of 4 done", 28, t["muted"])
    for i in range(4):
        rr(d, (64 + i * 236, 258, 64 + i * 236 + 220, 270), 6, fill=BLUE_L if i < 2 else t["line"])
    steps = [
        ("Connect Instagram", "@pixelwave.studio is connected", True),
        ("Add your brand colours", "3 colours saved", True),
        ("Pick your first campaign", "Choose a template to start from", False),
        ("Invite a teammate", "Optional, you can do this later", False),
    ]
    for i, (title, sub, done) in enumerate(steps):
        y = 330 + i * 190
        cur = i == 2
        rr(d, (64, y, W - 64, y + 160), 26, fill=t["card"], outline=BLUE_L if cur else t["line"], w=4 if cur else 2)
        if done:
            tick(d, 130, y + 80, 28, GREEN_L, "#FFFFFF")
        else:
            d.ellipse((102, y + 52, 158, y + 108), outline=BLUE_L if cur else t["line"], width=4)
        text(d, (190, y + 38), title, 34, t["text"], True)
        text(d, (190, y + 92), sub, 26, t["muted"])
        if cur:
            d.line((W - 120, y + 62, W - 100, y + 80, W - 120, y + 98), fill=BLUE_L, width=5, joint="curve")
    rr(d, (64, 1160, W - 64, 1264), 52, fill=t["text"])
    text(d, (W / 2, 1212), "Continue", 36, t["card"], True, "mm")
    return img


def attendance_phone() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    status_bar(d, t)
    text(d, (64, 124), "CSE-B  ·  Semester 5", 28, t["muted"])
    text(d, (64, 168), "Today", 64, t["text"], True)
    text(d, (64, 252), "Thursday, 23 October", 28, t["muted"])
    rr(d, (64, 308, W - 64, 388), 20, fill="#FFF4DB")
    d.ellipse((92, 336, 112, 356), fill=AMBER_L)
    text(d, (130, 328), "Offline. 2 marks waiting to sync.", 28, "#7A5200")
    classes = [
        ("9:00", "Data Structures", "LH-204", "Present"),
        ("10:00", "Database Systems", "LH-204", "Present"),
        ("11:45", "Operating Systems Lab", "Lab 3", "Absent"),
        ("2:00", "Engineering Maths III", "LH-110", "Not marked"),
    ]
    for i, (time, course, room, status) in enumerate(classes):
        y = 420 + i * 168
        rr(d, (64, y, W - 64, y + 148), 24, fill=t["card"], outline=t["line"])
        text(d, (96, y + 30), time, 30, t["text"], True)
        text(d, (96, y + 80), "pm" if time in ("2:00",) else "am", 24, t["muted"])
        d.line((190, y + 24, 190, y + 124), fill=t["line"], width=2)
        text(d, (222, y + 28), course, 32, t["text"], True)
        text(d, (222, y + 84), room, 26, t["muted"])
        bg, fg = {"Present": ("#DDF5EA", GREEN_L), "Absent": ("#FBE0E3", RED_L), "Not marked": ("#ECEEF2", t["muted"])}[status]
        pill(d, W - 92, y + 46, status, 26, bg, fg, right=True)
    text(d, (64, 1128), "This month", 26, t["muted"])
    text(d, (64, 1166), "92%", 72, t["text"], True)
    text(d, (W - 64, 1198), "Needs 75% to sit exams", 26, t["muted"], anchor="ra")
    rr(
        d,
        (
            64,
            1262,
            W - 64,
            1280,
        ),
        9,
        fill=t["line"],
    )
    rr(d, (64, 1262, 64 + (W - 128) * 0.92, 1280), 9, fill=GREEN_L)
    return img


KEYWORDS = {
    "export",
    "async",
    "function",
    "const",
    "for",
    "of",
    "await",
    "try",
    "catch",
    "if",
    "return",
    "throw",
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "BY",
    "HAVING",
    "ORDER",
    "COUNT",
    "AS",
    "DESC",
    "UPDATE",
    "SET",
}
TOKEN = re.compile(r'(//.*$)|("(?:[^"\\]|\\.)*")|([A-Za-z_]\w*)|(\d+)|(\s+)|(.)')


def code_line(d: Draw, x: float, y: float, line: str, size: int, t: dict) -> None:
    pitch = size * 0.58
    pos = 0
    for m in TOKEN.finditer(line):
        s = m.group(0)
        if m.group(1):
            col = t["muted"]
        elif m.group(2):
            col = GREEN
        elif m.group(3):
            col = VIOLET if s in KEYWORDS else (BLUE if line[m.end() : m.end() + 1] == "(" else t["text"])
        elif m.group(4):
            col = AMBER
        else:
            col = t["text"]
        mono(d, x + pos * pitch, y, s, size, col)
        pos += len(s)


def code_screen(tabs: list[str], lines: list[str], status: str, start: int = 1) -> Image.Image:
    t = DARK
    img, d = canvas(t)
    d.rectangle((0, 0, W, 110), fill="#0B0D11")
    x = 0.0
    for i, tab in enumerate(tabs):
        w = width(d, tab, 28) + 64
        if i == 0:
            d.rectangle((x, 0, x + w, 110), fill=t["bg"])
            d.rectangle((x, 106, x + w, 110), fill=BLUE)
        text(d, (x + 32, 36), tab, 28, t["text"] if i == 0 else t["muted"])
        x += w
    for i, line in enumerate(lines):
        y = 150 + i * 50
        text(d, (96, y), str(start + i), 28, "#4A5163", anchor="ra")
        code_line(d, 140, y, line, 30, t)
    d.rectangle((0, H - 70, W, H), fill="#0B0D11")
    text(d, (32, H - 52), status, 25, t["muted"])
    return img


def sync_code() -> Image.Image:
    lines = [
        "export async function syncPending(db: Db) {",
        "  const rows = await db.all(",
        '    "SELECT * FROM marks WHERE synced = 0"',
        "  );",
        "  for (const row of rows) {",
        "    try {",
        '      await api.post("/attendance", row);',
        "      await db.run(",
        '        "UPDATE marks SET synced = 1 WHERE id = ?",',
        "        [row.id],",
        "      );",
        "    } catch (err) {",
        "      // offline: keep the row, retry on reconnect",
        "      if (!isOffline(err)) throw err;",
        "      return;",
        "    }",
        "  }",
        "}",
    ]
    return code_screen(["sync.ts", "db.ts", "App.tsx"], lines, "TypeScript   Ln 13, Col 8   UTF-8")


def dedupe_sql() -> Image.Image:
    t = DARK
    lines = ["SELECT isbn, COUNT(*) AS copies", "FROM books", "GROUP BY isbn", "HAVING COUNT(*) > 1", "ORDER BY copies DESC;"]
    img = code_screen(["dedupe.sql", "library.csv"], lines, "SQLite   books.db   412 rows   0.04 s")
    d = ImageDraw.Draw(img)
    rr(d, (60, 440, W - 60, 1230), 22, fill=t["card"], outline=t["line"])
    text(d, (92, 470), "isbn", 26, t["muted"])
    text(d, (W - 92, 470), "copies", 26, t["muted"], anchor="ra")
    rows = [
        ("978-0-13-468599-1", 6),
        ("978-81-203-4078-6", 5),
        ("978-0-262-03384-8", 5),
        ("978-93-5260-120-3", 4),
        ("978-0-13-110362-7", 4),
        ("978-81-317-1633-0", 3),
        ("978-0-596-51774-8", 3),
        ("978-81-203-3532-4", 2),
    ]
    for i, (isbn, n) in enumerate(rows):
        y = 530 + i * 82
        d.line((92, y - 14, W - 92, y - 14), fill=t["line"], width=2)
        mono(d, 92, y + 6, isbn, 30, t["text"])
        text(d, (W - 92, y + 6), str(n), 30, AMBER if n > 4 else t["text"], anchor="ra")
    return img


def deal_log() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    text(d, (60, 64), "Deal log", 56, t["text"], True)
    text(d, (60, 138), "Month 7 of 9  ·  six open conversations", 28, t["muted"])
    stage = {
        "Intro": ("#ECEEF2", t["muted"]),
        "Demo": ("#E3EEFF", BLUE_L),
        "Pilot": ("#EFE8FF", "#5B3DF0"),
        "Procurement": ("#FFF1D6", AMBER_L),
        "Won": ("#DDF5EA", GREEN_L),
        "Stalled": ("#FBE0E3", RED_L),
    }
    rows = [
        ("CSIR-NCL, Pune", "Procurement", "22.0L", "Legal is reviewing the MoU"),
        ("IISER Bhopal", "Pilot", "9.5L", "Three labs are testing it"),
        ("NCBS, Bengaluru", "Demo", "14.0L", "Demo booked for 28 Oct"),
        ("BITS Hyderabad core lab", "Won", "6.8L", "Purchase order received"),
        ("ARCI, Hyderabad", "Intro", "12.0L", "Their tech lead replied"),
        ("IIT Kanpur photonics", "Stalled", "16.0L", "Waiting on a grant decision"),
    ]
    for i, (org, st, val, note) in enumerate(rows):
        y = 210 + i * 150
        rr(d, (60, y, W - 60, y + 130), 22, fill=t["card"], outline=t["line"])
        text(d, (92, y + 24), org, 31, t["text"], True)
        text(d, (92, y + 76), note, 25, t["muted"])
        bg, fg = stage[st]
        pill(d, W - 92, y + 22, st, 24, bg, fg, right=True)
        money(d, W - 92, y + 108, val, 30, t["text"], True, right=True)
    rr(d, (60, 1128, W - 60, 1296), 22, fill="#F1F5FF")
    d.rectangle((60, 1128, 70, 1296), fill=BLUE_L)
    text(d, (96, 1150), "What moved deals this month", 25, BLUE_L, True)
    text(d, (96, 1194), "A named technical contact asked for a pilot.", 29, t["text"], True)
    text(d, (96, 1240), "Price was never the first question.", 28, t["muted"])
    return img


def serial_monitor() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    d.rectangle((0, 0, W, 120), fill="#00878F")
    text(d, (48, 40), "COM4  ·  9600 baud", 34, "#FFFFFF", True)
    text(d, (W - 48, 46), "Autoscroll", 26, "#E0F4F5", anchor="ra")
    readings = [
        (41, "OFF"),
        (40, "OFF"),
        (38, "OFF"),
        (37, "OFF"),
        (35, "OFF"),
        (34, "ON"),
        (34, "ON"),
        (36, "ON"),
        (39, "ON"),
        (43, "ON"),
        (46, "OFF"),
        (45, "OFF"),
        (44, "OFF"),
        (42, "OFF"),
        (41, "OFF"),
        (39, "OFF"),
        (37, "OFF"),
        (35, "OFF"),
        (34, "ON"),
    ]
    for i, (m, pump) in enumerate(readings):
        y = 160 + i * 52
        sec = 11 + i * 2
        a0 = 12 * m + 120
        on = pump == "ON"
        if on:
            d.rectangle((0, y - 8, W, y + 42), fill="#E4F6EC")
        mono(d, 40, y, f"12:04:{sec:02d}  A0={a0}  moisture={m}%  pump={pump}", 27, GREEN_L if on else t["text"])
    d.rectangle((0, H - 110, W, H), fill="#E8EAEE")
    rr(d, (32, H - 90, W - 230, H - 28), 12, fill="#FFFFFF", outline=t["line"])
    text(d, (52, H - 74), "threshold 35", 28, t["muted"])
    rr(d, (W - 200, H - 90, W - 32, H - 28), 12, fill="#00878F")
    text(d, (W - 116, H - 59), "Send", 28, "#FFFFFF", True, "mm")
    return img


def bus_app() -> Image.Image:
    t = DARK
    img, d = canvas(t)
    status_bar(d, t)
    text(d, (64, 124), "Your stop", 26, t["muted"])
    text(d, (64, 166), "Hostel Gate", 62, t["text"], True)
    text(d, (64, 248), "Next buses", 28, t["muted"])
    buses = [
        ("27C", "Gandhipuram", "6 min", GREEN, "On time"),
        ("12", "Ukkadam", "11 min", GREEN, "On time"),
        ("S3", "Singanallur", "17 min", AMBER, "3 min late"),
        ("48", "Peelamedu", "24 min", GREEN, "On time"),
        ("70A", "Railway Station", "31 min", GREEN, "On time"),
    ]
    for i, (no, dest, eta, col, state) in enumerate(buses):
        y = 300 + i * 180
        rr(d, (64, y, W - 64, y + 156), 26, fill=t["card"], outline=t["line"])
        rr(d, (92, y + 34, 232, y + 122), 18, fill=BLUE if i % 2 == 0 else VIOLET)
        text(d, (162, y + 78), no, 40, "#FFFFFF", True, "mm")
        text(d, (264, y + 30), dest, 34, t["text"], True)
        d.ellipse((266, y + 94, 282, y + 110), fill=col)
        text(d, (296, y + 88), state, 25, col)
        text(d, (W - 96, y + 40), eta.split()[0], 56, t["text"], True, "ra")
        text(d, (W - 96, y + 108), "min", 24, t["muted"], anchor="ra")
    text(d, (64, 1230), "Updated 12 seconds ago", 25, t["muted"])
    return img


def figma_frames() -> Image.Image:
    t = DARK
    img, d = canvas(t)
    d.rectangle((0, 0, 270, H), fill="#1A1A1F")
    d.rectangle((W - 290, 0, W, H), fill="#1A1A1F")
    text(d, (24, 40), "Layers", 26, t["muted"])
    layers = [
        ("Profile card", 0, True),
        ("Avatar", 1, False),
        ("Name", 1, False),
        ("Role", 1, False),
        ("Message button", 1, False),
    ]
    for i, (name, ind, sel) in enumerate(layers):
        y = 100 + i * 60
        if sel:
            d.rectangle((0, y - 8, 270, y + 44), fill="#12335E")
        text(d, (24 + ind * 32, y), name, 26, t["text"])
    text(d, (W - 266, 40), "Auto layout", 26, t["muted"])
    props = [("Direction", "Vertical"), ("Gap", "8"), ("Padding", "16"), ("Width", "Hug"), ("Corner radius", "12")]
    for i, (k, v) in enumerate(props):
        y = 110 + i * 110
        text(d, (W - 266, y), k, 24, t["muted"])
        rr(d, (W - 266, y + 38, W - 24, y + 84), 10, fill="#26262D")
        text(d, (W - 248, y + 48), v, 26, t["text"])
    d.rectangle((270, 0, W - 290, H), fill="#232329")
    cx0, cy0 = 330, 330
    rr(d, (cx0, cy0, cx0 + 400, cy0 + 440), 12, fill="#FFFFFF")
    d.rectangle((cx0 - 4, cy0 - 4, cx0 + 404, cy0 + 444), outline="#0D99FF", width=3)
    d.ellipse((cx0 + 16, cy0 + 16, cx0 + 112, cy0 + 112), fill="#C9D6FF")
    text(d, (cx0 + 64, cy0 + 64), "S", 44, "#3B4A8F", True, "mm")
    text(d, (cx0 + 16, cy0 + 138), "Sakthi Vel", 34, "#14171F", True)
    text(d, (cx0 + 16, cy0 + 190), "Backend mentor, Chennai", 25, "#6B7280")
    text(d, (cx0 + 16, cy0 + 236), "Can help with APIs, hiring", 25, "#6B7280")
    rr(d, (cx0 + 16, cy0 + 340, cx0 + 384, cy0 + 408), 10, fill="#14171F")
    text(d, (cx0 + 200, cy0 + 374), "Message", 28, "#FFFFFF", True, "mm")
    for x, y, lab in [(cx0 + 8, cy0 + 8, "16"), (cx0 + 8, cy0 + 316, "16")]:
        rr(d, (x - 4, y - 2, x + 38, y + 30), 6, fill="#F24E9B")
        text(d, (x + 17, y + 14), lab, 22, "#FFFFFF", True, "mm")
    text(d, (cx0 + 200, cy0 - 40), "Profile card  ·  400 x 440", 24, "#0D99FF", anchor="ma")
    return img


def cold_email() -> Image.Image:
    t = LIGHT
    img, d = canvas(t)
    status_bar(d, t)
    text(d, (64, 124), "Inbox", 28, BLUE_L, True)
    text(d, (64, 172), "Re: Frontend internship, third-year at SRM", 44, t["text"], True)
    rr(d, (64, 290, W - 64, 900), 26, fill=t["card"], outline=t["line"])
    d.ellipse((96, 322, 164, 390), fill="#DDF5EA")
    text(d, (130, 356), "A", 34, GREEN_L, True, "mm")
    text(d, (190, 322), "Anitha Rao", 32, t["text"], True)
    text(d, (190, 366), "Founder, Greenloop", 25, t["muted"])
    text(d, (W - 96, 330), "10:42", 26, t["muted"], anchor="ra")
    body = [
        "Hi Karthik,",
        "Thanks for the note and for linking your portfolio. The attendance app is close to what we need for our field team.",
        "Can you do a 20 minute call tomorrow at 4 pm? Bring one idea for the onboarding screen.",
        "Anitha",
    ]
    y = 440
    for para in body:
        for line in wrap(d, para, 29, W - 64 * 2 - 64):
            text(d, (96, y), line, 29, t["text"])
            y += 44
        y += 20
    rr(d, (64, 940, 440, 1030), 45, fill=t["text"])
    text(d, (252, 985), "Reply", 32, t["card"], True, "mm")
    d.line((64, 1090, W - 64, 1090), fill=t["line"], width=2)
    text(d, (64, 1116), "Your message, 22 Oct", 25, t["muted"])
    quote = "I am a third-year CSE student at SRM. I built an attendance app that works offline, and I would like to help your field team."
    for i, line in enumerate(wrap(d, quote, 27, W - 128)[:3]):
        text(d, (64, 1166 + i * 40), line, 27, t["muted"])
    return img


SCENES: dict[str, Callable[[], Image.Image]] = {
    "turnaround_tracker": turnaround_tracker,
    "investor_update": investor_update,
    "hiring_board": hiring_board,
    "assay_run": assay_run,
    "onboarding_phone": onboarding_phone,
    "attendance_phone": attendance_phone,
    "sync_code": sync_code,
    "dedupe_sql": dedupe_sql,
    "deal_log": deal_log,
    "serial_monitor": serial_monitor,
    "bus_app": bus_app,
    "figma_frames": figma_frames,
    "cold_email": cold_email,
}


def render(scene: str) -> bytes:
    """A PNG (4:5) of one named screen. Same scene, same bytes."""
    buf = io.BytesIO()
    SCENES[scene]().save(buf, "PNG", optimize=True)
    return buf.getvalue()
