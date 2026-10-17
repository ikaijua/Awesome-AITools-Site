#!/usr/bin/env python3
"""Generate the bilingual directory from one pinned Awesome-AITools commit."""

import argparse
from datetime import datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/ikaijua/Awesome-AITools"
FILES = {"zh": "README-CN.md", "en": "README.md"}


def markdown_links(value):
    """Replace Markdown links/images, including balanced URL parentheses."""
    pattern = re.compile(r"(!?)\[([^\]\n]*)\]\(")
    text, links, pos = [], [], 0
    while match := pattern.search(value, pos):
        text.append(value[pos:match.start()])
        end, depth = match.end(), 1
        while end < len(value) and depth:
            if value[end] == "(" and (end == 0 or value[end - 1] != "\\"):
                depth += 1
            elif value[end] == ")" and (end == 0 or value[end - 1] != "\\"):
                depth -= 1
            end += 1
        if depth:
            raise ValueError(f"Unclosed Markdown link: {value[match.start():]}")
        if not match[1]:
            label, url = match[2], value[match.end():end - 1].strip()
            if url.startswith("<") and ">" in url:
                url = url[1:url.index(">")]
            else:
                url = re.split(r'\s+[\"\']', url, maxsplit=1)[0]
            links.append({"label": label, "url": html.unescape(url)})
            text.append(label)
        pos = end
    text.append(value[pos:])
    return "".join(text), links


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.active = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "li", "div"}:
            self.parts.append(" ")
        if tag == "a":
            self.active = {"url": dict(attrs).get("href", ""), "parts": []}

    def handle_endtag(self, tag):
        if tag == "a" and self.active:
            self.links.append({"label": "".join(self.active["parts"]), "url": self.active["url"]})
            self.active = None
        if tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_data(self, data):
        self.parts.append(data)
        if self.active:
            self.active["parts"].append(data)


def plain(value):
    text, md_links = markdown_links(value)
    parser = PlainHTML()
    parser.feed(text)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"\*\*|__|`+", "", text).replace("\\|", "|")
    return re.sub(r"\s+", " ", text).strip(), md_links + parser.links


def resolve_url(url, filename):
    result = urljoin(f"{REPOSITORY}/blob/main/{filename}", url)
    parsed = urlsplit(result)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Unsupported link: {url}")
    return result


def parse_readme(text, filename):
    tools, category = [], None
    table = False
    for line_number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if line.startswith("#"):
            table = False
            category = plain(line[4:])[0] if line.startswith("### ") else None
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line[1:])]
        if cells[-1] == "":
            cells.pop()
        if cells and cells[0] in {"Name", "名称"}:
            if len(cells) != 4 or not category:
                raise ValueError(f"Unexpected table header: {filename}:{line_number}")
            table = True
            continue
        if not table or all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
            continue
        # Upstream robot rows omit the fourth (pricing) cell.
        if len(cells) == 3:
            cells.append("")
        if len(cells) != 4:
            raise ValueError(f"Expected 3 or 4 cells: {filename}:{line_number}")
        name, name_links = plain(cells[0])
        description, description_links = plain(cells[1])
        _, primary_links = plain(cells[2])
        fee, _ = plain(cells[3])
        more, links, seen = "", [], set()
        for link in primary_links + name_links + description_links:
            url = resolve_url(link["url"], filename)
            if url in seen:
                continue
            seen.add(url)
            if not more and url.startswith(REPOSITORY + "/discussions/"):
                more = url
            else:
                links.append({"label": plain(link["label"])[0] or "URL", "url": url})
        # A linked tool name or discussion can be its only navigable URL.
        if not links and more:
            links.append({"label": "GitHub Discussions", "url": more})
            more = ""
        if not name or not description or not links:
            raise ValueError(f"Incomplete entry: {filename}:{line_number}: {name}")
        tools.append({
            "name": name.replace("🌟", "").strip(),
            "description": description.replace("🌟", "").strip(),
            "category": category,
            "fee": fee,
            "links": links,
            "more": more,
            "featured": "🌟" in cells[0] + cells[1],
        })
    if not tools:
        raise ValueError(f"No tool table found in {filename}")
    return tools


def get(url):
    request = Request(url, headers={"User-Agent": "Awesome-AITools-Site-sync", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def load_source(source, ref):
    if source:
        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], text=True, encoding="utf-8")
        commit = git("rev-parse", ref + "^{commit}").strip()
        timestamp = git("show", "-s", "--format=%cI", commit).strip()
        readmes = {lang: git("show", f"{commit}:{filename}") for lang, filename in FILES.items()}
    else:
        head = json.loads(get("https://api.github.com/repos/ikaijua/Awesome-AITools/commits/" + ref))
        commit, timestamp = head["sha"], head["commit"]["committer"]["date"]
        readmes = {lang: get(f"https://raw.githubusercontent.com/ikaijua/Awesome-AITools/{commit}/{filename}") for lang, filename in FILES.items()}
    # Normalize the timestamp to UTC so local and remote sources generate identical data.
    from datetime import timezone
    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"repository": REPOSITORY, "commit": commit, "committedAt": timestamp, "updatedAt": timestamp[:10], "files": FILES}, readmes


def generate(meta, readmes):
    return {"meta": meta, **{lang: parse_readme(readmes[lang], filename) for lang, filename in FILES.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Read a local upstream Git repository instead of GitHub")
    parser.add_argument("--ref", default="main", help="Upstream commit or ref (default: main)")
    parser.add_argument("--check", action="store_true", help="Fail if the committed snapshot differs; do not write")
    args = parser.parse_args()
    meta, readmes = load_source(args.source, args.ref)
    data = generate(meta, readmes)
    target = ROOT / "site/data.json"
    index = ROOT / "site/index.html"
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    index_before = index.read_text(encoding="utf-8")
    note = f"内容来自项目 README · 收录快照：{meta['updatedAt'].replace('-', '.')} · 功能与费用请以工具官网为准"
    index_after, replacements = re.subn(r'(?<=id="dataNote">)[^<]+', lambda _: note, index_before)
    if replacements != 1:
        raise ValueError("Expected exactly one snapshot note in index.html")
    if args.check:
        if target.read_text(encoding="utf-8") != rendered or index_before != index_after:
            raise SystemExit("Snapshot differs; run scripts/sync_upstream.py without --check")
    else:
        # Validate both languages completely before replacing either generated file.
        for path, value in ((target, rendered), (index, index_after)):
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(value, encoding="utf-8")
            temporary.replace(path)
    print(json.dumps({"commit": meta["commit"], "date": meta["updatedAt"], **{lang: {"tools": len(data[lang]), "categories": len({t['category'] for t in data[lang]})} for lang in FILES}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
