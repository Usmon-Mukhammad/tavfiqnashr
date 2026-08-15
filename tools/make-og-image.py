#!/usr/bin/env python3
"""Build the 1200x630 Open Graph card for TAVFIQNASHR.

Mirrors the layout used on ofiyatmed.uz (brand gradient, logo top-left,
wordmark, tracked subtitle, hairline rule, contact row) in this site's
palette: deep green + gold on cream.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, sys

import os
LANG = (sys.argv[1] if len(sys.argv) > 1 else "uz")
SUBTITLE = {"uz": "NASHRIYOTI", "ru": "\u0418\u0417\u0414\u0410\u0422\u0415\u041b\u042c\u0421\u0422\u0412\u041e"}[LANG]
TAGLINE  = {"uz": "O'qiladigan kitoblar bulog'i",
            "ru": "\u0420\u043e\u0434\u043d\u0438\u043a \u043a\u043d\u0438\u0433, \u0434\u043e\u0441\u0442\u043e\u0439\u043d\u044b\u0445 \u043f\u0440\u043e\u0447\u0442\u0435\u043d\u0438\u044f"}[LANG]
OUT = {"uz": "assets/og-image.png", "ru": "assets/og-image-ru.png"}[LANG]

W, H = 1200, 630
GREEN      = (15, 61, 51)
GREEN_DEEP = (7, 34, 28)
GOLD       = (201, 163, 74)
GOLD_SOFT  = (184, 145, 47)
CREAM      = (250, 246, 236)
MUTED      = (163, 186, 178)

SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS    = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def f(path, size):
    return ImageFont.truetype(path, size)

# ---------- background: diagonal gradient, deep green ----------
bg = Image.new("RGB", (W, H), GREEN)
px = bg.load()
for y in range(H):
    for x in range(0, W, 2):
        t = (x / W) * 0.55 + (y / H) * 0.45
        c = tuple(int(GREEN[i] + (GREEN_DEEP[i] - GREEN[i]) * t) for i in range(3))
        px[x, y] = c
        if x + 1 < W:
            px[x + 1, y] = c

# warm glow behind the wordmark
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([-260, -300, 780, 470], fill=(70, 56, 20))
glow = glow.filter(ImageFilter.GaussianBlur(150))
bg = Image.blend(bg, Image.blend(bg, glow, 0.0), 0.0)
bg = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), bg,
                     Image.new("L", (W, H), 0))  # no-op guard
base = Image.new("RGB", (W, H))
base.paste(bg)
base = Image.blend(base, glow.point(lambda v: v), 0.18)
# re-darken edges so the glow reads as light, not wash
vig = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.ellipse([-300, -340, 820, 500], fill=90)
vig = vig.filter(ImageFilter.GaussianBlur(160))
base = Image.composite(Image.blend(base, Image.new("RGB", (W, H), GREEN), 0.0), base, vig)

img = base
d = ImageDraw.Draw(img)

# ---------- geometric ornament, right side (Islamic 8-point star grid) ----------
orn = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(orn)
step = 78
for cy in range(-step, H + step, step):
    for cx in range(W - 470, W + step, step):
        r = step * 0.46
        pts8 = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
                for a in range(0, 360, 45)]
        od.polygon(pts8, outline=(201, 163, 74, 42))
        pts4 = [(cx + r * 0.62 * math.cos(math.radians(a + 22.5)),
                 cy + r * 0.62 * math.sin(math.radians(a + 22.5)))
                for a in range(0, 360, 90)]
        od.polygon(pts4, outline=(201, 163, 74, 30))
# fade the ornament out toward the left
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
for x in range(W - 470, W):
    v = int(255 * ((x - (W - 470)) / 470) ** 1.5)
    md.line([(x, 0), (x, H)], fill=v)
orn.putalpha(Image.composite(orn.split()[3], Image.new("L", (W, H), 0), mask))
img = Image.alpha_composite(img.convert("RGBA"), orn).convert("RGB")
d = ImageDraw.Draw(img)

M = 96  # left margin

# ---------- logo, circular, top-left ----------
logo = Image.open("assets/img/logo.jpg").convert("RGB")
LS = 132
logo = logo.resize((LS, LS), Image.LANCZOS)
cm = Image.new("L", (LS * 4, LS * 4), 0)
ImageDraw.Draw(cm).ellipse([0, 0, LS * 4 - 1, LS * 4 - 1], fill=255)
cm = cm.resize((LS, LS), Image.LANCZOS)
ring = Image.new("RGB", (LS + 8, LS + 8), GOLD)
rm = Image.new("L", ((LS + 8) * 4, (LS + 8) * 4), 0)
ImageDraw.Draw(rm).ellipse([0, 0, (LS + 8) * 4 - 1, (LS + 8) * 4 - 1], fill=110)
rm = rm.resize((LS + 8, LS + 8), Image.LANCZOS)
img.paste(ring, (M - 4, 92 - 4), rm)
img.paste(logo, (M, 92), cm)

# ---------- wordmark ----------
d.text((M, 268), "TAVFIQNASHR", font=f(SERIF_B, 92), fill=CREAM)

# tracked-out subtitle
sub, sx, sf = SUBTITLE, M, f(SANS, 27)
for ch in sub:
    d.text((sx, 384), ch, font=sf, fill=GOLD)
    sx += sf.getlength(ch) + 7

# ---------- hairline rule ----------
d.line([(M, 452), (W - M, 452)], fill=(255, 255, 255), width=1)
d.line([(M, 452), (M + 190, 452)], fill=GOLD, width=2)

# ---------- bottom row ----------
d.text((M, 492), "@tavfiqnashr  ·  +998 97 521 67 00",
       font=f(SANS_B, 27), fill=CREAM)
d.text((M, 536), "tavfiqnashr.uz", font=f(SANS, 24), fill=MUTED)

# Tagline sits on the lower row, right-aligned. The Russian string is much
# longer than the Uzbek one, so keeping it on the contact row overlapped the
# phone number; this row only holds the short domain on the left.
tag = TAGLINE
tf = f(SANS_B, 26)
tag_x = W - M - tf.getlength(tag)
domain_right = M + f(SANS, 24).getlength("tavfiqnashr.uz")
assert tag_x > domain_right + 40, f"tagline overlaps domain: {tag_x} vs {domain_right}"
d.text((tag_x, 534), tag, font=tf, fill=GOLD_SOFT)

img.save(OUT, "PNG", optimize=True)
print("wrote", OUT, img.size)
