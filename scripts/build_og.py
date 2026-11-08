#!/usr/bin/env python3
"""Render per-page Open Graph cards (1200×630) for tool and category pages.

One shared card for the whole site makes every shared link look identical, so
each tool page and category page gets its own PNG: name, category, fee, and a
one-line summary. Cards are generated at build time from site/data.json and
written into dist/og/<lang>/... to match the paths used by build_site.head().
"""

import argparse
import json
import os
import re
from hashlib import sha1
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import build_site

W, H = 1200, 630
PAD = 72
BG = "#0B0E14"
FG = "#F5F7FA"
MUTED = "#98A2B3"
DIM = "#6B7686"
ACCENTS = ["#F97316", "#38BDF8", "#A78BFA", "#34D399", "#F472B6", "#FACC15", "#22D3EE", "#FB7185", "#60A5FA", "#FBBF24"]

FONT_CANDIDATES = {
    True: [
        (str(Path.home() / "Library/Fonts/NotoSansCJKsc-Bold.otf"), 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ],
    False: [
        (str(Path.home() / "Library/Fonts/NotoSansCJKsc-Regular.otf"), 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 2),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ],
}

_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key in _cache:
        return _cache[key]
    candidates = list(FONT_CANDIDATES[bold])
    env_key = "OG_FONT_BOLD" if bold else "OG_FONT_REGULAR"
    env_value = os.environ.get(env_key)
    if env_value:
        path, _, index = env_value.partition(":")
        candidates.insert(0, (path, int(index or 0)))
    for path, index in candidates:
        try:
            face = ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
        _cache[key] = face
        return face
    raise SystemExit(
        "找不到中文字体：请安装 fonts-noto-cjk，或设置 %s 指定字体文件路径（可选 路径:index）" % env_key
    )


def accent(name):
    return ACCENTS[int(sha1(name.encode("utf-8")).hexdigest(), 16) % len(ACCENTS)]


def wrap(draw, text, face, max_width, max_lines):
    """Greedy wrap that keeps ASCII words intact and ellipsises the last line."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    lines, current = [], ""
    for token in re.findall(r"[!-~]+|\s+|\S", text):
        probe = current + token
        if draw.textlength(probe, font=face) <= max_width or not current:
            current = probe
            continue
        lines.append(current.rstrip())
        current = token
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and draw.textlength("".join(lines), font=face) < draw.textlength(text, font=face):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=face) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip(" ，。、,.;:") + "…"
    return lines


def tracked(draw, xy, text, face, fill, spacing=6):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=face, fill=fill)
        x += draw.textlength(ch, font=face) + spacing


def chip(draw, xy, text, face, fg, bg, pad_x=20, pad_y=12, radius=999):
    x, y = xy
    w = draw.textlength(text, font=face) + pad_x * 2
    h = face.size + pad_y * 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=min(radius, h // 2), fill=bg)
    draw.text((x + pad_x, y + pad_y - face.size * 0.12), text, font=face, fill=fg)
    return w, h


def card(title, desc, *, label, tag, footer_left, footer_right, out, glow):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Soft accent glow in the top-right corner, clipped to the canvas.
    layer = Image.new("RGB", (W, H), BG)
    dl = ImageDraw.Draw(layer)
    for i in range(28, 0, -1):
        r = 90 + i * 9
        alpha = int(2.2 + i * 0.5)
        dl.ellipse([W - 240 - r, -180 - r + 40, W - 240 + r, -180 + r + 40], fill=_mix(BG, glow, alpha / 100))
    img = Image.blend(img, layer, 0.85)
    d = ImageDraw.Draw(img)

    # Left accent bar keeps the card recognisable as one series.
    d.rectangle([0, 0, 10, H], fill=glow)

    tracked(d, (PAD + 6, 62), label, font(22, True), DIM, spacing=5)

    tag_w, tag_h = chip(d, (PAD, 116), tag, font(26, True), "#0B0E14", glow, pad_x=22, pad_y=11)

    title_face = font(78, True) if len(title) <= 14 else font(66, True)
    lines = wrap(d, title, title_face, W - PAD * 2 - 40, 2)
    y = 196
    for line in lines:
        d.text((PAD, y), line, font=title_face, fill=FG)
        y += int(title_face.size * 1.18)

    desc_face = font(30)
    dy = min(max(y + 34, 350), 396)
    for line in wrap(d, desc, desc_face, W - PAD * 2 - 60, 3):
        d.text((PAD, dy), line, font=desc_face, fill=MUTED)
        dy += int(desc_face.size * 1.55)

    d.line([(PAD, H - 104), (W - PAD, H - 104)], fill="#1E2430", width=2)
    right_face, left_face = font(26), font(26)
    right_w = d.textlength(footer_right, font=right_face)
    avail = W - PAD * 2 - right_w - 24
    left = footer_left
    while left and d.textlength(left, font=left_face) > avail:
        left = left[:-1]
    if left != footer_left:
        left = left.rstrip(" ·") + "…"
    d.text((PAD, H - 76), left, font=left_face, fill=DIM)
    d.text((W - PAD - right_w, H - 76), footer_right, font=right_face, fill=DIM)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def _mix(base, tint, ratio):
    a = tuple(int(base[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(tint[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(int(a[i] + (b[i] - a[i]) * ratio) for i in range(3))


def build(dist, base_url, only=None):
    data = json.loads((build_site.ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    pages = json.loads((build_site.ROOT / "site" / "tool_pages.json").read_text(encoding="utf-8"))
    routes = build_site.category_routes(data)
    known = {lang: {row[i]: row[0] for row in build_site.CATEGORIES if row[i]} for i, lang in ((1, "zh"), (2, "en"))}

    made = []
    for lang in ("zh", "en"):
        zh = lang == "zh"
        home = base_url if zh else base_url + "en/"
        label = "AWESOME AI TOOLS" if not zh else "AWESOME AI TOOLS · 精选清单"
        domain = "ikaijua.github.io"

        by_name = {}
        for tool in data[lang]:
            by_name.setdefault(tool["name"], tool)

        # Tool pages: only the curated ones that actually exist as pages. EN pages
        # fall back to the zh name, mirroring build_site's tool page resolution.
        for slug, names in pages.items():
            name = names.get(lang) or names.get("zh")
            tool = by_name.get(name) if name else None
            if not tool:
                continue
            out = dist / "og" / lang / "tools" / f"{slug}.png"
            if only and only not in str(out):
                continue
            desc = build_site.clean_description(tool["description"])
            fee = tool["fee"] or ("未标明" if zh else "Unspecified")
            footer_left = (f"费用：{fee}" if zh else f"Pricing: {fee}")
            made.append(card(
                name, desc,
                label=label,
                tag=tool["category"],
                footer_left=f"{footer_left}  ·  " + (f"共 {len(data[lang])} 个工具 · 每周更新" if zh else f"{len(data[lang])} tools · updated weekly"),
                footer_right=domain,
                out=out, glow=accent(tool["category"]),
            ))

        # Category pages: intro line plus the top tools, so the card says why to click.
        for category, path in routes[lang].items():
            slug = path.split("/categories/")[1].strip("/")
            tools = [t["name"] for t in data[lang] if t["category"] == category]
            intro = build_site.INTROS.get(slug, ("", ""))[0 if zh else 1]
            desc = intro or (f"{len(tools)} 个工具，按用途与费用整理。" if zh else f"{len(tools)} tools, grouped by use case and pricing.")
            out = dist / "og" / lang / "categories" / f"{slug}.png"
            if only and only not in str(out):
                continue
            made.append(card(
                category,
                f"{desc} " + ("如 " if zh else "Examples: ") + "、".join(tools[:3]) if zh else f"{desc} Examples: {', '.join(tools[:3])}",
                label=label,
                tag=(f"{len(tools)} 个工具" if zh else f"{len(tools)} tools"),
                footer_left=(f"共 {len(data[lang])} 个工具 · 每周更新" if zh else f"{len(data[lang])} tools · updated weekly"),
                footer_right=domain,
                out=out, glow=accent(category),
            ))
    return {"cards": len(made)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default=str(build_site.ROOT / "dist"))
    parser.add_argument("--base-url", default=json.loads((build_site.ROOT / "site.config.json").read_text())["url"])
    parser.add_argument("--only", default=None, help="只生成路径包含该子串的卡片（调试用）")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.outdir), args.base_url, args.only), ensure_ascii=False))


if __name__ == "__main__":
    main()
