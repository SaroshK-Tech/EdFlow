"""Generate title screens and lower thirds (PNG, 1280x720) for the demo film.

Professional look: dark navy gradient, subtle dot grid texture, ambient glow,
letter-spaced kickers, the real logo01 lockup on the open/close cards, and
sleeker lower thirds with an accent tab, hairline and brand pill.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "work" / "assets"
LOGO_FILE = ROOT.parent / "logo01.png"
ASSETS.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720

NAVY = (10, 16, 34)
NAVY_TOP = (14, 22, 46)
NAVY_BOTTOM = (6, 10, 24)
ACCENT = (74, 168, 255)
ACCENT_DIM = (58, 132, 205)
AMBER = (255, 196, 66)
WHITE = (255, 255, 255)
GREY = (154, 165, 186)
GREY_DIM = (106, 118, 142)
BAR_BG = (24, 36, 70)
PLATE = (30, 44, 82)


def font(size, bold=True, heavy=False):
    names = ["segoeuib.ttf", "seguisb.ttf"]
    if bold and not heavy:
        names = ["seguisb.ttf", "segoeuib.ttf"]
    if heavy:
        names = ["segoeuib.ttf"]
    for fname in names:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{fname}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def tracked(draw, xy, text, fnt, fill, tracking=0, anchor="la"):
    """Draw text with letter-spacing (PIL lacks native tracking)."""
    x, y = xy
    total = 0
    if anchor.startswith("m"):
        for ch in text:
            total += draw.textlength(ch, font=fnt) + tracking
        x -= total / 2
    elif anchor.startswith("r"):
        for ch in text:
            total += draw.textlength(ch, font=fnt) + tracking
        x -= total
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def gradient():
    img = Image.new("RGB", (W, H), NAVY_BOTTOM).convert("RGBA")
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(NAVY_TOP[0] * (1 - t) + NAVY_BOTTOM[0] * t)
        g = int(NAVY_TOP[1] * (1 - t) + NAVY_BOTTOM[1] * t)
        b = int(NAVY_TOP[2] * (1 - t) + NAVY_BOTTOM[2] * t)
        d.line([(0, y), (W, y)], fill=(r, g, b, 255))
    return img


def glow(img, cx, cy, radius, color, strength=70):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    steps = 48
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        a = int(strength * (1 - i / steps) ** 2.2)
        od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, a))
    overlay = overlay.filter(ImageFilter.GaussianBlur(12))
    return Image.alpha_composite(img, overlay)


def dot_grid(img, spacing=46, alpha=10):
    d = ImageDraw.Draw(img)
    for y in range(spacing // 2, H, spacing):
        for x in range(spacing // 2, W, spacing):
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(216, 228, 248, alpha))
    return img


_logo_cache = None


def load_logo():
    global _logo_cache
    if _logo_cache is None:
        _logo_cache = Image.open(LOGO_FILE).convert("RGBA")
    return _logo_cache


def paste_logo(img, cx, top, width, radius=26):
    """Paste logo01 centered on cx at `top`, width px, with rounded corners."""
    logo = load_logo()
    ratio = width / logo.width
    h = int(logo.height * ratio)
    logo = logo.resize((width, h), Image.LANCZOS)
    mask = Image.new("L", logo.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, logo.width, logo.height], radius=radius, fill=255)
    paste = Image.new("RGBA", img.size, (0, 0, 0, 0))
    paste.paste(logo, (int(cx - width / 2), top), mask)
    return Image.alpha_composite(img, paste)


def draw_rule(draw, cx, y, half=200, color=AMBER, thickness=4):
    seg = 58
    draw.rectangle([(cx - half, y), (cx - half + seg, y + thickness)], fill=color)
    draw.rectangle([(cx + half - seg, y), (cx + half, y + thickness)], fill=color)
    draw.rectangle([(cx - 6, y), (cx + 6, y + thickness)], fill=(*WHITE,))


def bottom_bar(draw, left, right):
    f_small = font(15, bold=False)
    f_small_b = font(15, bold=True)
    bar_y = H - 46
    draw.line([(40, bar_y - 14), (W - 40, bar_y - 14)], fill=(44, 58, 100, 255))
    tracked(draw, (44, bar_y + 2), left, f_small_b, (200, 210, 230), tracking=2)
    w = 0
    for ch in right:
        w += draw.textlength(ch, font=f_small) + 2
    tracked(draw, (W - 44 - w, bar_y + 2), right, f_small, GREY_DIM, tracking=2)


def title_card(kind):
    img = gradient()
    img = dot_grid(img)
    img = glow(img, W // 2, 210, 480, ACCENT, strength=34)
    d = ImageDraw.Draw(img)

    splash = kind.get("splash")
    closing = kind.get("closing")

    if splash or closing:
        logo_w = 952 if splash else 800
        logo_top = 96 if splash else 108
        img = paste_logo(img, W // 2, logo_top, logo_w)

        f_kick = font(19, bold=True)
        f_main = font(56, bold=True)
        f_sub = font(27, bold=False)
        f_line = font(19, bold=False)

        kick_y = 330 if splash else 316
        tracked(d, (W // 2, kick_y), kind.get("kicker", "PRODUCT DEMONSTRATION"),
                f_kick, ACCENT, tracking=6, anchor="ma")

        main_y = kick_y + 52
        d.text((W // 2 - d.textlength(kind["main"], font=f_main) / 2, main_y),
               kind["main"], font=f_main, fill=WHITE)
        line_y = main_y + 96
        draw_rule(d, W // 2, line_y, half=210, color=AMBER, thickness=4)

        sub_y = line_y + 26
        d.text((W // 2 - d.textlength(kind["sub"], font=f_sub) / 2, sub_y),
               kind["sub"], font=f_sub, fill=(178, 196, 226))

        if kind.get("line"):
            ly = sub_y + 56
            tracked(d, (W // 2, ly), kind["line"], f_line, GREY, tracking=3, anchor="ma")

        bottom_bar(d, "© 2026 AlgoriSync Ltd", "Version 1.0  ·  Local Deployment  ·  Windows Server")
    else:
        logo_w = 196
        img = paste_logo(img, W // 2, 118, logo_w, radius=14)

        f_kick = font(17, bold=True)
        f_main = font(52, bold=True)
        f_sub = font(23, bold=False)
        f_line = font(17, bold=False)

        y0 = 322
        tracked(d, (W // 2, y0), kind.get("kicker", "EDFLOW · BY ALGORISYNC"),
                f_kick, GREY, tracking=6, anchor="ma")
        d.text((W // 2 - d.textlength(kind["main"], font=f_main) / 2, y0 + 46),
               kind["main"], font=f_main, fill=WHITE)
        draw_rule(d, W // 2, y0 + 132, half=170, color=AMBER, thickness=4)
        d.text((W // 2 - d.textlength(kind["sub"], font=f_sub) / 2, y0 + 158),
               kind["sub"], font=f_sub, fill=(178, 196, 226))
        if kind.get("line"):
            tracked(d, (W // 2, y0 + 210), kind["line"], f_line,
                    GREY_DIM, tracking=3, anchor="ma")
        bottom_bar(d, "EdFlow By AlgoriSync", kind.get("corner", "Product Demonstration"))

    img = img.convert("RGB")
    img.save(ASSETS / f"{kind['file']}.png")
    print("wrote", ASSETS / f"{kind['file']}.png")


def lower_third(key, label):
    left, sep, right = label.partition("\u00b7")
    main_txt = left.strip()
    sub_txt = right.strip()

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    y = 596
    h = 84
    x0 = 44

    f_main = font(30, bold=True)
    f_sub = font(16, bold=False)
    f_pill = font(14, bold=True)

    main_w = d.textlength(main_txt, font=f_main)
    sub_w = d.textlength(sub_txt, font=f_sub)
    content_w = max(main_w, sub_w if sub_txt else 0)
    pill_w = 260
    box_w = int(content_w + 96)
    x1 = x0 + box_w

    d.rounded_rectangle([(x0, y), (x1, y + h)], radius=12, fill=(14, 21, 42, 232))
    d.rounded_rectangle([(x0, y), (x0 + 10, y + h)], radius=5, fill=(*ACCENT, 255))
    d.line([(x0 + 10, y + 6), (x1, y + 6)], fill=(74, 168, 255, 90))

    d.text((x0 + 36, y + 18), main_txt, font=f_main, fill=WHITE)
    if sub_txt:
        d.text((x0 + 36, y + h - 38), sub_txt.upper(), font=f_sub,
               fill=(140, 160, 190), spacing=0)
        tracked(d, (x0 + 36, y + h - 24), "", f_sub, (140, 160, 190), tracking=2)

    pill_x = x1 - pill_w - 26
    pill_y = y + 20
    pill_h = 44
    d.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
                        radius=22, outline=(74, 168, 255, 180), width=2)
    tracked(d, (pill_x + pill_w // 2, pill_y + 14), "EDFLOW BY ALGORISYNC",
            f_pill, (74, 168, 255), tracking=2, anchor="ma")

    tracked(d, (W - 46, H - 36), "EDFLOW BY ALGORISYNC", font(15, bold=True),
            (205, 215, 235, 150), tracking=4, anchor="ra")
    img.save(ASSETS / f"lower_{key}.png")
    print("wrote lower", key)


def main():
    from narration import LOWER_THIRDS, TITLES

    title_card({
        "file": "title_open", "splash": True,
        "main": TITLES["open"][0], "sub": TITLES["open"][1],
        "kicker": "PRODUCT DEMONSTRATION · VERSION 1.0",
        "line": "One Windows server · one school · always connected, even when the internet is not",
    })
    title_card({
        "file": "title_close", "closing": True,
        "main": "Ready to deploy on your school network.",
        "sub": TITLES["close"][0],
        "kicker": "DEPLOY ON A LOCAL WINDOWS SERVER · POSTGRESQL · OFFLINE BY DESIGN",
        "line": "Documentation · Support · Training — included with every deployment",
    })

    for key in [
        "dashboard", "students", "timetable", "attendance", "fees", "finance",
        "payroll", "staff", "parents", "hardware", "communication",
        "notifications", "reports",
    ]:
        main_txt, sub_txt = TITLES[key]
        title_card({"file": f"title_{key}", "main": main_txt, "sub": sub_txt})

    for file, main_txt, sub_txt, line in [
        ("div_learning", "Students & Academics", "Records · attendance · master timetable",
         "The classroom, on record and offline"),
        ("div_finance", "Finance & People", "Fees · cash flow · payroll · staff",
         "Money and people, handled locally"),
        ("div_ops", "School Operations", "Hardware · maintenance · local communication",
         "The campus, connected without the cloud"),
        ("div_platform", "The Offline Platform", "Reports · exports · announcements",
         "No internet required — by design"),
    ]:
        title_card({"file": file, "main": main_txt, "sub": sub_txt, "line": line})

    for key, label in LOWER_THIRDS.items():
        lower_third(key, label)

    print("ASSETS DONE")


if __name__ == "__main__":
    main()