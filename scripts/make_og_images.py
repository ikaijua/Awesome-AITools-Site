#!/usr/bin/env python3
"""Render the Open Graph share images used by og:image.

Pillow is only needed on the machine that regenerates the artwork, never in
CI: the committed PNGs under site/og/ are copied into dist/ verbatim.

    python3 scripts/make_og_images.py

Run this after changing the tagline or the brand colours in site/style.css.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "og"

WIDTH, HEIGHT = 1200, 630
BACKGROUND = "#262523"
ACCENT = "#d9fc73"
TEXT = "#f5f4ef"
MUTED = "#a3a29c"

FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_LATIN = "/System/Library/Fonts/SFNS.ttf"

COPIES = {
    "zh": {
        "kicker": "AI 工具导航",
        "title": "精选 AI 工具与开源项目",
        "subtitle": "按分类浏览 · 费用标注 · 官网直达",
        "footer": "ikaijua.github.io/Awesome-AITools-Site",
    },
    "en": {
        "kicker": "AI TOOL DIRECTORY",
        "title": "Curated AI Tools & Open Source",
        "subtitle": "Browse by category · Pricing notes · Official links",
        "footer": "ikaijua.github.io/Awesome-AITools-Site/en/",
    },
}


def font(size, latin=False):
    path = FONT_LATIN if latin else FONT_CJK
    return ImageFont.truetype(path, size)


def draw_asterisk(draw, center, radius, width):
    """Six-spoke mark matching the site brand glyph; drawn manually because
    system CJK fonts render U+2733 as a missing-glyph box."""
    import math

    cx, cy = center
    for angle in (90, 30, 150):
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        draw.line(
            [cx - dx * radius, cy + dy * radius, cx + dx * radius, cy - dy * radius],
            fill=ACCENT,
            width=width,
        )


def render(copy):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Accent frame keeps the card readable on both light and dark timelines.
    draw.rectangle([0, 0, WIDTH, 10], fill=ACCENT)
    draw_asterisk(draw, center=(102, 122), radius=32, width=12)
    draw.text((150, 104), copy["kicker"], font=font(34), fill=ACCENT)

    title_font = font(76)
    draw.text((76, 218), copy["title"], font=title_font, fill=TEXT)

    draw.text((78, 336), copy["subtitle"], font=font(32), fill=MUTED)

    draw.line([76, 420, WIDTH - 76, 420], fill="#3a3936", width=2)
    draw.text((76, 466), "Awesome AI Tools", font=font(38, latin=True), fill=TEXT)
    draw.text((76, 528), copy["footer"], font=font(26, latin=True), fill=MUTED)
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, copy in COPIES.items():
        target = OUT / f"{lang}.png"
        render(copy).save(target, optimize=True)
        print(target.relative_to(ROOT), f"{target.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
