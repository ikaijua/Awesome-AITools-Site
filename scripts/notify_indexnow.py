#!/usr/bin/env python3
"""Push the sitemap's URLs to IndexNow (Bing, Yandex, Naver, Seznam).

IndexNow is the push half of indexing: without it a rebuilt page waits for the
next crawl. Ownership is proven by site/<key>.txt, which the build publishes as
/<key>.txt, so the file name itself is the credential.

Fails soft on purpose: indexing must never block or fail a deploy.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_key() -> tuple[str, Path]:
    for path in sorted((ROOT / "site").glob("*.txt")):
        if re.fullmatch(r"[0-9a-f]{32}", path.stem):
            return path.stem, path
    raise SystemExit("site/ 下没有 32 位十六进制的 IndexNow key 文件")


def sitemap_urls(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", text)


def wait_for(url: str, timeout: int) -> bool:
    """GitHub Pages goes live a few seconds after the deploy step returns."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10) as response:
                if response.status < 400:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sitemap", default=str(ROOT / "dist" / "sitemap.xml"))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--endpoint", default="https://api.indexnow.org/indexnow")
    parser.add_argument("--wait", type=int, default=120, help="等待 key 文件可访问的秒数")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    key, key_file = find_key()
    urls = sitemap_urls(Path(args.sitemap))[: args.limit]
    if not urls:
        print("sitemap 为空，跳过", file=sys.stderr)
        return 1

    # The site can live on a project subpath, so the key file sits next to the
    # homepage rather than at the host root; keyLocation states it explicitly.
    home = min((url for url in urls if url.endswith("/")), key=len, default=None)
    base = home or (urls[0].rsplit("/", 1)[0] + "/")
    host = re.sub(r"^https?://", "", base).split("/")[0]
    key_location = f"{base}{key}.txt"
    payload = {"host": host, "key": key, "keyLocation": key_location, "urlList": urls}

    print(f"IndexNow: {len(urls)} 个 URL · host={host} · key={key[:8]}…")
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False)[:300])
        return 0

    if not wait_for(key_location, args.wait):
        print(f"key 文件暂不可访问（{key_location}），跳过本次提交", file=sys.stderr)
        return 1

    request = urllib.request.Request(
        args.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"IndexNow 返回 HTTP {response.status}")
            return 0 if response.status < 300 else 1
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        print(f"IndexNow 失败 HTTP {error.code}: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"IndexNow 网络错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
