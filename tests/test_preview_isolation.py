import ast
import html
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
import web_documents

ROOT=Path(web_documents.__file__).parent


def rendered_preview(document):
    node=next(n for n in ast.parse((ROOT/'app.py').read_text(encoding='utf-8')).body
              if isinstance(n,ast.FunctionDef) and n.name=='preview_document')
    class Sink:
        frame=''
        def markdown(self,value,**_):self.frame=value
    sink=Sink()
    namespace={**vars(web_documents),'st':sink,'html':html,'re':re}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-preview-renderer>','exec'),namespace)
    namespace['preview_document'](document,'Audit preview')
    return sink.frame


class PreviewIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hits=[]
        class Canary(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.hits.append(self.path)
                self.send_response(200);self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers();self.wfile.write(b'Harmless audit canary')
            def log_message(self,*_):pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Canary)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop()
        cls.server.shutdown();cls.server.server_close()

    def setUp(self):
        self.hits.clear()
        self.context=self.browser.new_context()
        self.page=self.context.new_page()

    def tearDown(self):self.context.close()

    def test_quoted_head_cannot_bypass_network_policy(self):
        document=f'<html><head data-test=">quoted"><script>fetch("http://127.0.0.1:{self.server.server_port}/quoted-head").catch(()=>{{}})</script></head><body>Canary</body></html>'
        self.page.set_content(rendered_preview(document));self.page.wait_for_timeout(600)
        self.assertEqual(self.hits,[], 'Untrusted preview reached the local network canary')

    def test_child_frame_cannot_navigate_to_network(self):
        document=f'<html><body><script>location.href="http://127.0.0.1:{self.server.server_port}/navigation"</script></body></html>'
        self.page.set_content(rendered_preview(document));self.page.wait_for_timeout(600)
        self.assertEqual(self.hits,[], 'Frame navigation escaped the network restriction')

    def test_real_interaction_still_works(self):
        document='<html><body><button onclick="document.getElementById(\'value\').textContent=\'1\'">Increase</button><output id="value">0</output></body></html>'
        self.page.set_content(rendered_preview(document))
        boundary=self.page.locator('iframe[title="Preview isolation boundary"]')
        frame=(self.page.frame_locator('iframe[title="Preview isolation boundary"]').frame_locator('iframe[title="Audit preview"]')
               if boundary.count() else self.page.frame_locator('iframe[title="Audit preview"]'))
        frame.get_by_role('button',name='Increase',exact=True).click()
        expect(frame.locator('#value')).to_have_text('1')
        frames=self.page.locator('iframe')
        self.assertNotIn('allow-same-origin',frames.first.get_attribute('sandbox'))

    def test_local_form_handler_works_without_network_submission(self):
        document='<html><body><form onsubmit="event.preventDefault();document.getElementById(\'result\').textContent=\'Validated locally\'"><input aria-label="Name" required><button type="submit">Validate</button></form><output id="result">Waiting</output></body></html>'
        self.page.set_content(rendered_preview(document))
        frame=self.page.frame_locator('iframe[title="Preview isolation boundary"]').frame_locator('iframe[title="Audit preview"]')
        frame.get_by_label('Name').fill('Audit')
        frame.get_by_role('button',name='Validate',exact=True).click()
        expect(frame.locator('#result')).to_have_text('Validated locally',timeout=2000)

    def test_real_form_submission_is_still_blocked(self):
        document=f'<html><body><form action="http://127.0.0.1:{self.server.server_port}/form-canary" method="get"><button type="submit">Submit</button></form><script>document.querySelector("form").submit()</script></body></html>'
        self.page.set_content(rendered_preview(document));self.page.wait_for_timeout(600)
        self.assertEqual(self.hits,[])

    def test_submitted_markup_cannot_escape_into_parent(self):
        document='<html><body></iframe><script>try{parent.document.body.dataset.auditEscaped="yes"}catch(e){document.body.textContent="Parent blocked"}</script></body></html>'
        self.page.set_content(rendered_preview(document))
        self.page.wait_for_timeout(150)
        self.assertIsNone(self.page.locator('body').get_attribute('data-audit-escaped'))


class PreviewSerializationTests(unittest.TestCase):
    def test_multiline_source_cannot_terminate_markdown_html_block(self):
        source='<html><body>\n\n<output id="value">0</output>\n\n<script>// Preserve this line ending\ndocument.getElementById("value").textContent="1";</script></body></html>'
        frame=rendered_preview(source)
        self.assertNotIn('\n',frame)
        self.assertIn('&#10;',html.unescape(frame))
