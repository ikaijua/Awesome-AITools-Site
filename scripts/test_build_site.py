from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

import build_site


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.canonicals, self.alternates, self.scripts = [], [], {}, []
        self.ids, self.names = set(), []
        self.description = ""
        self.language = ""
        self.title = ""
        self.h1_count = 0
        self.active = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.add(a['id'])
        if tag == 'html':
            self.language = a.get('lang')
        if tag == 'h1':
            self.h1_count += 1
        if tag in {'a', 'link'} and 'href' in a:
            self.links.append(a['href'])
        if tag in {'img', 'script'} and 'src' in a:
            self.links.append(a['src'])
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonicals.append(a['href'])
        if tag == 'link' and a.get('rel') == 'alternate':
            self.alternates[a['hreflang']] = a['href']
        if tag == 'meta' and a.get('name') == 'description':
            self.description = a.get('content', '')
        if tag in {'title', 'h3'} or tag == 'script' and a.get('type') in {'application/json', 'application/ld+json'}:
            self.active = [tag, a.get('type'), '']

    def handle_data(self, value):
        if self.active:
            self.active[2] += value

    def handle_endtag(self, tag):
        if self.active and self.active[0] == tag:
            if tag == 'h3':
                self.names.append(self.active[2])
            elif tag == 'title':
                self.title = self.active[2]
            elif tag == 'script':
                self.scripts.append(json.loads(self.active[2]))
            self.active = None


class BuiltSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / 'dist'
        cls.base = 'https://example.github.io/Awesome-AITools-Site/'
        cls.summary = build_site.build(cls.output, cls.base)
        cls.pages = {}
        # Google ownership-verification HTML files are assets, not indexed pages.
        for path in cls.output.rglob('index.html'):
            relative = path.relative_to(cls.output).as_posix()
            url = cls.base + relative.removesuffix('index.html')
            cls.pages[url] = Page(path.read_text())
        cls.data = json.loads((build_site.ROOT / 'site/data.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_every_tool_is_readable_without_javascript(self):
        for lang in ('zh', 'en'):
            actual = []
            for url, page in self.pages.items():
                if f'/{lang}/categories/' in url:
                    actual.extend(page.names)
            self.assertCountEqual(actual, [tool['name'] for tool in self.data[lang]])
        self.assertGreater(len(self.pages[self.base].names), 0)
        self.assertGreater(len(self.pages[self.base + 'en/'].names), 0)

    def test_all_internal_links_and_assets_resolve_on_pages_subpath(self):
        prefix = urlsplit(self.base).path
        for current, page in self.pages.items():
            for href in page.links:
                target = urlsplit(urljoin(current, href))
                if target.netloc != urlsplit(self.base).netloc:
                    continue
                self.assertTrue(target.path.startswith(prefix), (current, href))
                path = self.output / unquote(target.path.removeprefix(prefix))
                if target.path.endswith('/'):
                    path /= 'index.html'
                self.assertTrue(path.is_file(), (current, href, str(path)))
                if target.fragment and path.suffix == '.html':
                    target_page = Page(path.read_text())
                    self.assertIn(target.fragment, target_page.ids, (current, href))

    def test_sitemap_and_page_canonicals_match_exactly(self):
        tree = ET.parse(self.output / 'sitemap.xml')
        urls = [element.text for element in tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertCountEqual(urls, self.pages)
        self.assertEqual(len(set(urls)), len(urls))
        for url, page in self.pages.items():
            self.assertEqual(page.canonicals, [url])
            self.assertEqual(page.h1_count, 1)
            self.assertTrue(page.description)
        self.assertEqual(len({page.title for page in self.pages.values()}), len(self.pages))

    def test_language_alternates_are_reciprocal_and_exist(self):
        for url, page in self.pages.items():
            self.assertIn(url, page.alternates.values())
            for code, target in page.alternates.items():
                self.assertIn(target, self.pages)
                if code != 'x-default':
                    self.assertEqual(self.pages[target].language, code)
                    self.assertEqual(self.pages[target].alternates[page.language], url)

    def test_json_payload_is_safe_in_html(self):
        self.assertNotIn('</script>', build_site.script_json({'value': '</script><script>alert(1)</script>'}))

    def test_root_domain_and_project_robots_differ(self):
        self.assertFalse((self.output / 'robots.txt').exists())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'dist'
            build_site.build(output, 'https://example.org/')
            self.assertIn('Sitemap: https://example.org/sitemap.xml', (output / 'robots.txt').read_text())

    def test_new_upstream_category_gets_a_stable_link(self):
        data = {'zh': [{'category': '未来分类'}], 'en': []}
        routes = build_site.category_routes(data)
        self.assertEqual(routes, build_site.category_routes(data))
        self.assertTrue(routes['zh']['未来分类'].startswith('zh/categories/category-'))

    def test_invalid_base_url_is_rejected(self):
        for value in ('relative/path', 'javascript:alert(1)', 'https://example.org/?key=value'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_site.build(self.output, value)


if __name__ == '__main__':
    unittest.main()
