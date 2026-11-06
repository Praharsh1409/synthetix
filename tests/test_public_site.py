from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[]
    def handle_starttag(self,tag,attrs):
        identifier=dict(attrs).get('id')
        if identifier:self.ids.append(identifier)


class PublicSiteTests(unittest.TestCase):
    def test_counter_and_copy_controls_match_their_script(self):
        page=Page();page.feed((ROOT/'docs/index.html').read_text(encoding='utf-8'))
        required=re.findall(r"getElementById\('([^']+)'\)",(ROOT/'docs/site.js').read_text(encoding='utf-8'))
        for identifier in required:
            with self.subTest(identifier=identifier):self.assertEqual(page.ids.count(identifier),1)

    def test_public_copy_states_current_ai_availability(self):
        for path in ('README.md','docs/index.html','docs/app.html'):
            source=(ROOT/path).read_text(encoding='utf-8')
            with self.subTest(path=path):self.assertIn('unavailable',source.lower())
