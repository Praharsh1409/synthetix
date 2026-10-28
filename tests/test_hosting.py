import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import MagicMock,patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright,expect
import hosting
from local_host import make_handler


class HostHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.sites=Path(self.temp.name)/'sites';self.sites.mkdir()
        self.site=self.sites/('a'*32);self.site.mkdir()
        (self.site/'index.html').write_text('<html><body>Audit page</body></html>')
        (self.site/'site.json').write_text(json.dumps({'title':'Audit site'}))
        self.token='audit-only-control-secret'
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.sites,self.token))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.temp.cleanup()

    def test_public_health_does_not_disclose_control_token(self):
        try:
            with urlopen(self.base+'/_synthetix_health') as response:status=response.status;body=response.read()
        except HTTPError as error:status=error.code;body=error.read()
        self.assertEqual(status,403)
        self.assertNotIn(self.token.encode(),body)

    def test_authenticated_health_never_echoes_secret(self):
        request=Request(self.base+'/_synthetix_health',headers={'X-Synthetix-Token':self.token})
        with urlopen(request) as response:
            self.assertEqual(response.status,200);body=response.read()
        self.assertNotIn(self.token.encode(),body)
        self.assertEqual(json.loads(body)['service'],'synthetix-static-host')

    def test_unrecognized_host_header_is_rejected(self):
        request=Request(self.base+'/sites/'+self.site.name+'/',headers={'Host':'audit.invalid'})
        with self.assertRaises(HTTPError) as caught:urlopen(request)
        self.assertEqual(caught.exception.code,403)

    def test_root_and_traversal_are_not_served(self):
        for path in ['/.env','/../.env','/sites/'+self.site.name+'/../../.env','/sites/'+self.site.name+'/index.html']:
            with self.assertRaises(HTTPError) as caught:urlopen(self.base+path)
            self.assertEqual(caught.exception.code,404)

    def test_hosted_script_cannot_navigate_to_other_local_service(self):
        hits=[]
        class Canary(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path);self.send_response(200);self.end_headers()
            def log_message(self,*_):pass
        canary=ThreadingHTTPServer(('127.0.0.1',0),Canary)
        threading.Thread(target=canary.serve_forever,daemon=True).start()
        source=f'<html><body><script>location.href="http://127.0.0.1:{canary.server_port}/host-navigation"</script></body></html>'
        (self.site/'index.html').write_text(source)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch();page=browser.new_page()
                page.goto(self.base+'/sites/'+self.site.name+'/');page.wait_for_timeout(600)
                browser.close()
            self.assertEqual(hits,[])
            self.assertEqual((self.site/'index.html').read_text(),source)
        finally:canary.shutdown();canary.server_close()

    def test_hosted_interaction_works_without_changing_source(self):
        source='<html><body><button onclick="document.getElementById(\'value\').textContent=\'1\'">Increase</button><output id="value">0</output></body></html>'
        (self.site/'index.html').write_bytes(source.encode())
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page()
            page.goto(self.base+'/sites/'+self.site.name+'/')
            scope=page.frame_locator('iframe') if page.locator('iframe').count() else page
            scope.get_by_role('button',name='Increase',exact=True).click()
            expect(scope.locator('#value')).to_have_text('1')
            browser.close()
        self.assertEqual((self.site/'index.html').read_bytes(),source.encode())


    def test_hosted_local_form_handler_works(self):
        source="""<html><body><form onsubmit="event.preventDefault();document.getElementById('result').textContent='Validated locally'"><input aria-label="Name" required><button type="submit">Validate</button></form><output id="result">Waiting</output></body></html>"""
        (self.site/'index.html').write_text(source)
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page()
            page.goto(self.base+'/sites/'+self.site.name+'/')
            scope=page.frame_locator('iframe')
            scope.get_by_label('Name').fill('Audit')
            scope.get_by_role('button',name='Validate',exact=True).click()
            expect(scope.locator('#result')).to_have_text('Validated locally',timeout=2000)
            browser.close()


class HostLifecycleTests(unittest.TestCase):
    def test_stop_does_not_claim_success_while_health_is_alive(self):
        record={'port':12345,'token':'audit-only-token'}
        response=MagicMock();response.__enter__.return_value.status=200
        with patch.object(hosting,'running_host',return_value=record),patch.object(hosting,'urlopen',return_value=response),patch.object(hosting.time,'monotonic',side_effect=[0,4]):
            self.assertFalse(hosting.stop_host())

    def test_startup_failure_returns_an_error_without_a_fake_url(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);process=MagicMock();process.poll.return_value=1
            with patch.object(hosting,'STATE',root/'server.json'),patch.object(hosting,'SITES',root/'sites'),patch.object(hosting,'running_host',return_value=None),patch.object(hosting.subprocess,'Popen',return_value=process):
                with self.assertRaisesRegex(RuntimeError,'could not start'):hosting.ensure_host()

    def test_available_port_used_when_another_port_is_occupied(self):
        occupied=socket.socket();occupied.bind(('127.0.0.1',0));occupied.listen()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                with patch.object(hosting,'STATE',root/'server.json'),patch.object(hosting,'SITES',root/'sites'):
                    try:
                        source='<html><body>Unmodified local source</body></html>'
                        site=hosting.publish_html(source,title='Port verification')
                        record=hosting.running_host()
                        self.assertNotEqual(record['port'],occupied.getsockname()[1])
                        with urlopen(site['url']) as response:self.assertEqual(response.status,200)
                        self.assertEqual((hosting.SITES/site['site_id']/'index.html').read_bytes(),source.encode())
                        self.assertTrue(hosting.stop_host())
                        self.assertIsNone(hosting.running_host())
                    finally:
                        hosting.stop_host()
        finally:occupied.close()
