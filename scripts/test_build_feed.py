import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build_feed

HEADER = (
    "# Awesome\n\n### 分类甲\n\n"
    "| 名称 | 说明 | 链接 | 费用 |\n"
    "| --- | --- | --- | --- |\n"
)


class BuildFeedTests(unittest.TestCase):
    """The feed must report first appearances only, never rewritten rows."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.write(HEADER + "| 工具一 | 第一个工具 | [官网](https://one.example) | 免费 |\n")
        self.commit("add tool one")
        self.write(
            HEADER
            + "| 工具一 | 说明被重写，不算新增 | [官网](https://one.example) | 免费 |\n"
            + "| 工具二 | [更多介绍](https://github.com/ikaijua/Awesome-AITools/discussions/1) "
            "第二个工具 | [官网](https://two.example) | 付费 |\n"
        )
        self.commit("rewrite one, add two")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout

    def write(self, text):
        (self.repo / "README-CN.md").write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "README-CN.md")
        self.git("commit", "-qm", message)

    def test_rewritten_rows_are_not_reported_as_new(self):
        items = build_feed.collect(self.repo, "README-CN.md", 10)
        self.assertEqual([item["name"] for item in items], ["工具二", "工具一"])
        self.assertEqual(items[0]["category"], "分类甲")
        self.assertEqual(items[0]["url"], "https://two.example")

    def test_feed_files_are_valid(self):
        output = Path(self.temp.name) / "dist"
        items = build_feed.write_feed(self.repo, output, "https://example.org/site", "README-CN.md", 10)
        self.assertEqual(len(items), 2)

        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = ET.parse(output / "feed.xml").getroot().findall("a:entry", ns)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].find("a:title", ns).text, "工具二 — 分类甲")
        self.assertEqual(entries[0].find("a:link", ns).get("href"), "https://two.example")
        self.assertTrue(all(entry.find("a:id", ns).text for entry in entries))

        data = json.loads((output / "feed.json").read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "https://jsonfeed.org/version/1.1")
        self.assertEqual(data["feed_url"], "https://example.org/site/feed.json")
        self.assertEqual([item["title"] for item in data["items"]], ["工具二", "工具一"])


if __name__ == "__main__":
    unittest.main()
