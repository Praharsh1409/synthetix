import unittest
from streamlit.testing.v1 import AppTest
from pathlib import Path
from canvas_story import render_story, SCENES

ROOT = Path(__file__).resolve().parents[1]

class CanvasStoryTests(unittest.TestCase):
    def test_story_is_inert_and_contains_complete_evidence(self):
        from html.parser import HTMLParser
        class Document(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags=[]; self.text=[]; self.inputs=[]
            def handle_starttag(self,tag,attrs):
                self.tags.append(tag)
                if tag=='input': self.inputs.append(dict(attrs))
            def handle_data(self,data): self.text.append(data)
        document=Document(); document.feed(render_story())
        self.assertFalse({'script','iframe','form'} & set(document.tags))
        text=' '.join(document.text)
        for name,title,description,evidence in SCENES:
            self.assertIn(title,text); self.assertIn(evidence,text)
        self.assertIn('Read the complete walkthrough',text)
        self.assertIn('Same check: select Interiors',text)
        self.assertIn('1 of 3 maximum',text)
        self.assertEqual(len(document.inputs),1)
        self.assertEqual(document.inputs[0]['type'],'range')
        self.assertEqual(document.inputs[0]['aria-label'],'Original and repaired comparison divider')

    def test_closing_cta_preserves_idea_and_enters_planning(self):
        app=AppTest.from_file(str(ROOT/'cloud_app.py')).run(timeout=25)
        app.text_area(key='studio_idea').set_value('A tiny architecture archive').run()
        next(b for b in app.button if b.label=='Start your project ↗').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key='planning_idea').value,'A tiny architecture archive')
        self.assertFalse(list((ROOT/'artifacts'/'visitors'/app.session_state['cloud_workspace_id']).glob('ui_jobs/*/request.json')))

    def test_authored_script_survives_streamlit_sanitizer(self):
        # DOMPurify SAFE_FOR_XML drops script text that resembles an HTML tag.
        # Comparisons use reversed operands where needed; protections stay enabled.
        import re
        script=(ROOT/'continuous_motion.js').read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'<[/\w!]',script))

    def test_reduced_motion_keeps_all_stages_in_document_flow(self):
        from unittest.mock import patch
        from browser_safety import isolated_page, load_document, empty_report
        # Authored CSS fixture; no API or application session involved.
        with patch('canvas_story.image_data',return_value='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
            story=render_story().replace('class="canvas-story"','class="canvas-story story-enhanced"')
        css=(ROOT/'canvas_story.css').read_text(encoding='utf-8')
        with isolated_page(empty_report()) as page:
            page.emulate_media(reduced_motion='reduce')
            load_document(page,'<!doctype html><style>'+css+'</style>'+story)
            self.assertEqual(page.locator('.story-pin').evaluate('(e)=>getComputedStyle(e).position'),'static')
            self.assertEqual(page.locator('.story-stack').evaluate('(e)=>getComputedStyle(e).transform'),'none')
            self.assertEqual(page.locator('.story-copy:visible').count(),8)
            self.assertEqual(page.locator('.story-still:visible').count(),8)
            self.assertTrue(page.get_by_role('button',name='Replay demonstration',exact=False).is_visible())
