import unittest
from sync_upstream import markdown_links, parse_readme


class ParseReadmeTests(unittest.TestCase):
    def parse(self, row):
        return parse_readme("### Tools\n| Name | Description | Links | Fees |\n| --- | --- | --- | --- |\n" + row, "README.md")[0]

    def test_links_and_markers_are_preserved_without_badge_images(self):
        tool = self.parse('| **Example** | 🌟 **Does work**<br>[Intro](https://github.com/ikaijua/Awesome-AITools/discussions/1) [Guide](https://example.org/guide) | [GitHub](https://github.com/example/tool) ![Stars](https://img.shields.io/github/stars/example/tool) | Free/Paid |')
        self.assertEqual(tool["name"], "Example")
        self.assertEqual(tool["description"], "Does work Intro Guide")
        self.assertTrue(tool["featured"])
        self.assertEqual(tool["more"], "https://github.com/ikaijua/Awesome-AITools/discussions/1")
        self.assertEqual([link["url"] for link in tool["links"]], ["https://github.com/example/tool", "https://example.org/guide"])

    def test_missing_robot_price_and_escaped_pipe(self):
        tool = self.parse(r'| Robot | Local A\|B control | [URL](https://example.org/) |')
        self.assertEqual(tool["fee"], "")
        self.assertEqual(tool["description"], "Local A|B control")

    def test_nested_parentheses_and_html_links(self):
        label, links = markdown_links('[Docs](https://example.org/wiki/Tool_(AI))')
        self.assertEqual(label, "Docs")
        self.assertEqual(links[0]["url"], "https://example.org/wiki/Tool_(AI)")
        tool = self.parse('| Tool | A &amp; B | <a href="https://example.org/?a=1&amp;b=2">Site</a> | Paid |')
        self.assertEqual(tool["description"], "A & B")
        self.assertEqual(tool["links"][0], {"label": "Site", "url": "https://example.org/?a=1&b=2"})

    def test_extra_description_links_and_relative_links(self):
        tool = self.parse('| Tool | [One](https://github.com/ikaijua/Awesome-AITools/discussions/1) [Two](https://github.com/ikaijua/Awesome-AITools/discussions/2) | [Docs](README-CN.md) | Free |')
        self.assertTrue(tool["links"][0]["url"].endswith('/blob/main/README-CN.md'))
        self.assertTrue(tool["links"][1]["url"].endswith('/discussions/2'))

    def test_invalid_rows_fail_instead_of_silently_skipping(self):
        for row in ('| Tool | Desc | [X](javascript:alert(1)) | Free |', '| Tool | Desc | | Free |', '| Tool | Desc | URL | Free | Extra |'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse(row)

    def test_only_tool_tables_are_imported(self):
        text = '### Introduction\n| A | B |\n| x | y |\n### Tools\n| Name | Description | Links | Fees |\n| --- | --- | --- | --- |\n| Good | Desc | [URL](https://example.org) | Free |\n## Articles\n| Ignore | Me |'
        self.assertEqual([tool["name"] for tool in parse_readme(text, "README.md")], ["Good"])


if __name__ == "__main__":
    unittest.main()
