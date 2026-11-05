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
        self.links, self.canonicals, self.alternates, self.scripts, self.meta = [], [], {}, [], []
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
        if tag == 'meta':
            self.meta.append((a.get('name') or a.get('property'), a))
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

    def test_open_graph_and_twitter_cards_use_existing_images(self):
        for url, page in self.pages.items():
            image = next((meta.get('content') for name, meta in page.meta if name == 'og:image'), None)
            self.assertTrue(image and image.startswith(self.base), url)
            self.assertTrue((self.output / image.removeprefix(self.base)).is_file(), image)
            card = next((meta.get('content') for name, meta in page.meta if name == 'twitter:card'), None)
            self.assertEqual(card, 'summary_large_image', url)

    def test_sitemap_carries_snapshot_lastmod(self):
        tree = ET.parse(self.output / 'sitemap.xml')
        lastmod = {element.text for element in tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')}
        self.assertEqual(lastmod, {self.data['meta']['updatedAt']})
        self.assertEqual(len(tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url')),
                         len(tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')))

    def test_llms_txt_lists_every_category_once_per_language(self):
        text = (self.output / 'llms.txt').read_text()
        self.assertIn(self.data['meta']['repository'], text)
        for lang in ('zh', 'en'):
            names = {tool['category'] for tool in self.data[lang]}
            for name in names:
                self.assertIn(f'[{name}](', text)

    def test_category_pages_expose_itemlist_jsonld(self):
        for url, page in self.pages.items():
            if '/categories/' not in url:
                continue
            lists = [script for script in page.scripts if script.get('@type') == 'ItemList']
            self.assertEqual(len(lists), 1, url)
            self.assertTrue(lists[0]['itemListElement'])

    def test_allowlisted_tools_get_pages_with_application_schema(self):
        spec = json.loads((build_site.ROOT / 'site/tool_pages.json').read_text())
        data_names = {lang: {tool['name'] for tool in self.data[lang]} for lang in ('zh', 'en')}
        expected = 0
        for slug, entry in spec.items():
            for lang in ('zh', 'en'):
                name = entry.get('en', entry['zh']) if lang == 'en' else entry['zh']
                if name not in data_names[lang]:
                    continue
                expected += 1
                url = self.base + f'{lang}/tools/{slug}/'
                self.assertIn(url, self.pages, slug)
                page = self.pages[url]
                self.assertIn(name, page.title, slug)
                self.assertEqual(page.h1_count, 1, slug)
                apps = [script for script in page.scripts if script.get('@type') == 'SoftwareApplication']
                self.assertEqual([app['name'] for app in apps], [name], slug)
        self.assertGreater(expected, 50)

    def test_category_and_homepage_cards_link_to_tool_pages(self):
        for tool in self.data['zh']:
            if tool['name'] == 'Cursor':
                category_url = self.base + 'zh/categories/ai-coding/'
                resolved = {urljoin(category_url, href) for href in self.pages[category_url].links}
                self.assertIn(self.base + 'zh/tools/cursor/', resolved)
        resolved = {urljoin(self.base, href) for href in self.pages[self.base].links}
        self.assertIn(self.base + 'zh/tools/chatgpt/', resolved)

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
