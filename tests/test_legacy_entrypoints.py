import contextlib
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import generate_ui,self_heal,synthetix,repair_test


class LegacyEntryPointTests(unittest.TestCase):
    def test_generation_cli_does_not_claim_execution_success(self):
        report={'javascript_errors':[],'console_errors':[],'execution_errors':['Browser unavailable']}
        with tempfile.TemporaryDirectory() as temp,patch.object(generate_ui,'PROJECT_FOLDER',Path(temp)),patch.object(generate_ui,'generate_html',return_value='<html>Audit</html>'),patch.object(generate_ui,'check_html',return_value=report),patch('builtins.input',return_value='Audit'),contextlib.redirect_stdout(io.StringIO()) as output:
            result=generate_ui.main()
            self.assertEqual(result,1)
            self.assertNotIn('No runtime errors were observed',output.getvalue())

    def test_main_cli_returns_nonzero_and_explains_failure(self):
        failure={'status':'repair_failed','error':'Audit model unavailable','output_folder':'audit-only'}
        with patch.object(synthetix,'run_pipeline',return_value=failure),patch('builtins.input',side_effect=['Audit','1']),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(synthetix.main(),1)
            self.assertIn('Audit model unavailable',output.getvalue())

    def test_old_self_heal_does_not_pass_when_browser_cannot_run(self):
        report={'javascript_errors':[],'console_errors':[],'execution_errors':['Browser unavailable']}
        with tempfile.TemporaryDirectory() as temp,patch.object(self_heal,'Path',return_value=Path(temp)/'self_heal.py'),patch.object(self_heal,'check_html',return_value=report),patch.object(self_heal,'check_button_behavior'),patch.object(self_heal,'request_repair') as repair,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self_heal.main(),1)
            repair.assert_not_called()

    def test_old_button_checker_has_the_same_network_boundary(self):
        hits=[]
        class Canary(BaseHTTPRequestHandler):
            def do_GET(self):hits.append(self.path);self.send_response(200);self.end_headers()
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Canary)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        source=f'<html><body><img src="http://127.0.0.1:{server.server_port}/legacy-canary"><button id="demo" onclick="document.getElementById(\'status\').textContent=\'Button works!\'">Test</button><p id="status">Button works!</p></body></html>'
        try:
            try:repair_test.check_button_behavior(source)
            except AssertionError:pass
            self.assertEqual(hits,[])
        finally:server.shutdown();server.server_close()
