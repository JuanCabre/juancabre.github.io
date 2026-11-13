"""Checks on the bibliography and on the built pages.

    python -m unittest discover -s tests -v
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build  # noqa: E402
from pipeline.prepare_data import TYPES, build_data  # noqa: E402
from pipeline.venues import new_names_notice  # noqa: E402

CONFIG = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))


class Bibliography(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_data(ROOT / 'data', CONFIG, '2000-01-01')
        cls.publications = cls.data['publications']

    def test_every_entry_lists_the_owner(self):
        self.assertEqual(self.data['meta']['entriesWithoutAuthor'], [])

    def test_no_entry_is_listed_twice(self):
        self.assertEqual(self.data['meta']['duplicateIds'], [])
        ids = [publication['id'] for publication in self.publications]
        self.assertEqual(len(ids), len(set(ids)))

    def test_entries_are_complete(self):
        for publication in self.publications:
            with self.subTest(entry=publication['id']):
                self.assertTrue(publication['title'])
                self.assertIn(publication['type'], TYPES)
                self.assertIsInstance(publication['year'], int)
                self.assertTrue(1990 < publication['year'] < 2100)
                self.assertEqual(len(publication['authors']), len(publication['people']))
                self.assertIn(self.data['author'], publication['people'])

    def test_links_are_web_addresses(self):
        for publication in self.publications:
            if publication['link']:
                with self.subTest(entry=publication['id']):
                    self.assertRegex(publication['link'], r'^https://\S+$')

    def test_professors_are_coauthors(self):
        self.assertEqual(self.data['meta']['unknownProfessors'], [],
                         'Names under "professors" in site.json must match a coauthor as shown on the site.')

    def test_venue_names_were_reviewed(self):
        self.assertFalse(new_names_notice(ROOT / 'data'),
                         'New venue names: run "python -m pipeline.venues --new" and review them.')


class BuiltSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.site = Path(cls.directory.name) / 'site'
        build.build(cls.site, 'https://example.org/', pdf='skip')  # printing needs a browser; CI builds with --pdf require
        cls.pages = sorted(cls.site.rglob('*.html'))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_all_pages_are_written(self):
        for target in build.PAGES.values():
            self.assertTrue((self.site / target).is_file(), target)
        self.assertTrue((self.site / build.CV_FILE).is_file())
        self.assertTrue((self.site / build.LIST_PAGE).is_file())
        self.assertTrue((self.site / '.nojekyll').is_file())

    def test_no_placeholder_is_left(self):
        for page in self.pages:
            with self.subTest(page=page.name):
                self.assertNotRegex(page.read_text(encoding='utf-8'), r'@@[A-Z0-9_]+(:[^@\s]+)?@@')

    def test_local_links_lead_somewhere(self):
        attribute = re.compile(r'(?:href|src)="([^"#?]+)[^"]*"')
        for page in self.pages:
            if page.name == '404.html':  # its links start at the site root
                continue
            for link in attribute.findall(page.read_text(encoding='utf-8')):
                if re.match(r'[a-z][a-z0-9+.-]*:', link) or link.startswith('//'):
                    continue
                target = (page.parent / link).resolve()
                if target.is_dir():
                    target = target / 'index.html'
                with self.subTest(page=str(page.relative_to(self.site)), link=link):
                    self.assertTrue(target.is_file(), f'{link} does not exist')

    def test_nothing_is_loaded_from_other_servers(self):
        external = re.compile(r'<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)="(https?:)?//[^"]+"[^>]*>')
        for page in self.pages:
            for tag in external.finditer(page.read_text(encoding='utf-8')):
                with self.subTest(page=page.name):
                    self.assertIn('rel="canonical"', tag[0], f'External resource: {tag[0]}')

    def test_printable_list_holds_every_entry(self):
        text = (self.site / build.LIST_PAGE).read_text(encoding='utf-8')
        data = json.loads((self.site / 'assets' / 'data' / 'publications.json').read_text(encoding='utf-8'))
        self.assertEqual(text.count('<li>'), len(data['publications']))

    def test_data_file_matches_the_bibliography(self):
        data = json.loads((self.site / 'assets' / 'data' / 'publications.json').read_text(encoding='utf-8'))
        entries = len(re.findall(r'^@\w+\{', (ROOT / 'data' / 'publications.bib').read_text(encoding='utf-8'), re.M))
        self.assertEqual(len(data['publications']) + data['meta']['duplicatesRemoved'], entries)


if __name__ == '__main__':
    unittest.main()
