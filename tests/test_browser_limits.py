import os
from pathlib import Path
import struct
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from playwright.sync_api import expect
import browser_check
from browser_safety import browser_environment,empty_report,isolated_page,load_document,record_error


class BrowserLimitTests(unittest.TestCase):
    def test_development_app_defaults_to_loopback(self):
        config=Path(browser_check.__file__).parent/'.streamlit'/'config.toml'
        self.assertEqual(tomllib.loads(config.read_text())['server']['address'],'127.0.0.1')

    def test_diagnostic_flood_is_bounded(self):
        messages=[]
        for _ in range(1000):record_error(messages,'x'*5000)
        self.assertEqual(len(messages),51)
        self.assertTrue(all(len(message)<=2000 for message in messages))

    def test_credentials_are_not_given_to_chromium(self):
        with patch.dict(os.environ,{'NEBIUS_API_KEY':'audit-only-key','AWS_SECRET_ACCESS_KEY':'audit-only-secret'}):
            environment=browser_environment()
            self.assertFalse('NEBIUS_API_KEY' in environment)
            self.assertFalse('AWS_SECRET_ACCESS_KEY' in environment)

    def test_screenshot_allocation_is_viewport_bounded(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(browser_check,'ARTIFACTS',Path(temp)):
            report=browser_check.check_html('<html><body style="height:100000px">Tall audit page</body></html>','tall.png')
            self.assertTrue(report['passed'],report.get('execution_errors'))
            data=Path(report['screenshot']).read_bytes()
            self.assertEqual(struct.unpack('>II',data[16:24]),(1280,720))

    def test_oversized_code_is_not_executed(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(browser_check,'ARTIFACTS',Path(temp)):
            report=browser_check.check_html('x'*100001,'too-large.png')
            self.assertFalse(report['passed'])
            self.assertTrue(report['execution_errors'])
            self.assertNotIn('screenshot',report)

    def test_file_canary_is_not_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'canary.txt';path.write_text('AUDIT_LOCAL_FILE_CANARY')
            source=f'<output id="result">Waiting</output><script>fetch({path.as_uri()!r}).then(r=>r.text()).then(t=>document.getElementById("result").textContent=t).catch(()=>document.getElementById("result").textContent="Blocked")</script>'
            report=empty_report()
            with isolated_page(report) as page:
                load_document(page,source)
                expect(page.locator('#result')).to_have_text('Blocked')

    def test_javascript_heap_has_a_declared_limit(self):
        report=empty_report()
        with isolated_page(report) as page:
            load_document(page,'<p>Audit heap policy</p>')
            limit=page.evaluate('performance.memory?.jsHeapSizeLimit || 0')
            self.assertGreater(limit,0)
            self.assertLessEqual(limit,256*1024*1024)
