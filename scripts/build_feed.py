#!/usr/bin/env python3
"""Generate Atom + JSON Feed of newly added tools from the upstream README history.

Why: the site has no ``<link rel="alternate">`` feed, and GitHub's
``commits/main.atom`` is a noisy stream (formatting, typo fixes, link repairs).
Aggregators, RSSHub and RSS-to-WeChat services cannot tell which commits actually
added a tool, so nobody republishes this list automatically.

An entry counts as new only when its row appears for the very first time.
Rows that were merely rewritten (flagship model refresh, wording tweak) are
excluded, otherwise every model upgrade would be reported as a new tool.

Usage:
    python3 scripts/build_feed.py --upstream ../Awesome-AITools --outdir dist
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

REPO_URL = "https://github.com/ikaijua/Awesome-AITools"
DEFAULT_SITE = "https://ikaijua.github.io/Awesome-AITools-Site"
LABELS = (
    "更多介绍", "更多信息", "对比", "开通ChatGPT订阅经验", "suno专题页面",
    "More Info", "Comparison", "Comparison post",
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def split_row(line: str) -> list[str]:
    """Split a markdown table row, ignoring pipes inside links and brackets."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, buf, depth_b, depth_p = [], [], 0, 0
    for ch in line:
        if ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b -= 1
        elif ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p -= 1
        if ch == "|" and depth_b == 0 and depth_p == 0:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells if len(cells) >= 3 else []


def strip_md(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)      # links -> label
    text = text.replace("<br>", " ").replace("</br>", " ")
    text = re.sub(r"\*\*(\d+)\.\s*", "", text)
    text = text.replace("**", "").replace("*", "")
    for label in LABELS:                                     # drop dangling link labels
        text = text.replace(label, " ")
    text = re.sub(r"^\s*\d+\.\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" |·-")


def primary_url(links_cell: str) -> str:
    urls = re.findall(r"\((https?://[^\s)]+)\)", links_cell)
    if not urls:
        urls = re.findall(r"(https?://[^\s|]+)", links_cell)
    for url in urls:
        if "img.shields.io" in url or "discussions/" in url:
            continue
        return url
    return urls[0] if urls else ""


def current_categories(repo: Path, readme: str) -> dict[str, str]:
    """name -> category, from the README as it stands now."""
    out: dict[str, str] = {}
    category = ""
    for line in (repo / readme).read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            category = line[4:].strip()
        elif line.startswith("| ") and not line.startswith("| 名称"):
            cells = split_row(line)
            if cells:
                out.setdefault(cells[0], category)
    return out


def collect(repo: Path, readme: str, limit: int) -> list[dict]:
    """Single pass over history (oldest -> newest), keeping first appearances."""
    categories = current_categories(repo, readme)
    try:
        patch = git(repo, "log", "-p", "--unified=0", "--reverse",
                    "--format=@@%H%x1f%ad%x1f%s", "--date=short", "--", readme)
    except subprocess.CalledProcessError as exc:                     # shallow clone
        raise SystemExit(f"git log failed (shallow clone? needs fetch-depth: 0): {exc.stderr[:200]}")

    first_seen: dict[str, dict] = {}
    sha = date = subject = ""
    for line in patch.splitlines():
        if line.startswith("@@"):
            parts = line[2:].split("\x1f")
            if len(parts) == 3:
                sha, date, subject = parts
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        if not body.startswith("| ") or body.startswith("| 名称"):
            continue
        cells = split_row(body)
        if len(cells) < 3 or set(cells[0]) <= {"-", " "} or not sha:
            continue
        name, desc, links = cells[0], cells[1], cells[2]
        fees = cells[3] if len(cells) > 3 else ""
        if name in first_seen:
            continue
        first_seen[name] = {
            "name": name,
            "category": categories.get(name, ""),
            "url": primary_url(links),
            "fees": strip_md(fees),
            "summary": strip_md(desc)[:400],
            "commit": sha[:7],
            "date": date,
            "subject": subject,
        }
    items = list(first_seen.values())
    return items[-limit:][::-1]


def build_atom(items: list[dict], updated: str, site: str) -> str:
    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "  <title>Awesome AI Tools · 新增收录</title>",
        f'  <link href="{site}/feed.xml" rel="self"/>',
        f'  <link href="{site}/"/>',
        f"  <id>{REPO_URL}/commits/main/</id>",
        f"  <updated>{updated}</updated>",
        "  <author><name>Awesome-AITools</name>"
        f"<uri>{REPO_URL}</uri></author>",
        "  <subtitle>只含真正新增的工具条目，过滤掉格式、链接修复与描述微调。</subtitle>",
        "  <generator>build_feed.py</generator>",
    ]
    for item in items:
        title = f"{item['name']} — {item['category']}" if item["category"] else item["name"]
        body = item["summary"] + (f"（费用：{item['fees']}）" if item["fees"] else "")
        tag = quote(f"{item['commit']}-{item['name']}".replace(" ", "-"))
        out += [
            "  <entry>",
            f"    <title>{esc(title)}</title>",
            f'    <link href="{esc(item["url"] or REPO_URL)}"/>',
            f"    <id>tag:github.com,2008:Awesome-AITools/{tag}</id>",
            f"    <updated>{item['date']}T00:00:00Z</updated>",
            f'    <category term="{esc(item["category"])}"/>',
            f"    <summary>{esc(body)}</summary>",
            "  </entry>",
        ]
    out.append("</feed>")
    return "\n".join(out)


def build_json(items: list[dict], site: str) -> str:
    data = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Awesome AI Tools · 新增收录",
        "home_page_url": f"{site}/",
        "feed_url": f"{site}/feed.json",
        "description": "只含真正新增的工具条目，过滤掉格式与链接修复。",
        "language": "zh-CN",
        "items": [
            {
                "id": f"{item['commit']}-{item['name']}",
                "url": item["url"] or REPO_URL,
                "title": item["name"],
                "content_text": item["summary"],
                "date_published": f"{item['date']}T00:00:00Z",
                "tags": [tag for tag in (item["category"], item["fees"]) if tag],
            }
            for item in items
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_feed(upstream: Path, outdir: Path, site: str = DEFAULT_SITE,
               readme: str = "README-CN.md", limit: int = 60) -> list[dict]:
    """Build feed.xml + feed.json into outdir; returns the emitted items."""
    items = collect(upstream, readme, limit)
    if not items:
        raise SystemExit("No new entries parsed — check the README version or git history")
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "feed.xml").write_text(build_atom(items, updated, site), encoding="utf-8")
    (outdir / "feed.json").write_text(build_json(items, site), encoding="utf-8")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default=".upstream",
                        help="Path to an Awesome-AITools checkout with full history")
    parser.add_argument("--outdir", default="dist")
    parser.add_argument("--site", default=DEFAULT_SITE, help="Public site base URL")
    parser.add_argument("--readme", default="README-CN.md")
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    upstream = Path(args.upstream).resolve()
    if not (upstream / args.readme).exists():
        raise SystemExit(f"{upstream}/{args.readme} not found — checkout the upstream repo first")
    items = write_feed(upstream, Path(args.outdir), args.site.rstrip("/"), args.readme, args.limit)
    print(f"feed: {len(items)} entries -> {args.outdir}/feed.xml, feed.json "
          f"({items[-1]['date']} .. {items[0]['date']})", file=sys.stderr)


if __name__ == "__main__":
    main()
