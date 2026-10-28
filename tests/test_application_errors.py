import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import browser_check,project_store,ui_worker,web_documents

ROOT=Path(web_documents.__file__).parent


class ApplicationErrorTests(unittest.TestCase):
    def test_syntax_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(browser_check,'ARTIFACTS',Path(temp)):
            result=browser_check.check_html('<html><script>function broken( {</script></html>','syntax.png')
            self.assertFalse(result['passed'])
            self.assertTrue(result['javascript_errors'])

    def test_console_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(browser_check,'ARTIFACTS',Path(temp)):
            result=browser_check.check_html('<html><script>console.error("audit console failure")</script></html>','console.png')
            self.assertFalse(result['passed'])
            self.assertIn('audit console failure',result['console_errors'])

    def test_failed_hosting_preserves_code_and_an_honest_summary(self):
        errors={'javascript_errors':[],'console_errors':[],'behavior_errors':[],'execution_errors':[]}
        report={**errors,'combined_errors':errors}
        with tempfile.TemporaryDirectory() as temp,patch.object(ui_worker,'ARTIFACTS',Path(temp)),patch.object(ui_worker,'check_version',return_value=report),patch.object(ui_worker,'publish_html',side_effect=RuntimeError('audit startup failure')):
            source='<html><body>Original source</body></html>'
            result=ui_worker.handle({'workflow':'host_code','html':source})
            self.assertFalse(result['ok'])
            self.assertEqual(result['summary']['status'],'hosting_failed')
            folder=Path(result['output_folder'])
            self.assertEqual((folder/'version_0.html').read_bytes(),source.encode())
            self.assertNotIn('local_site',result['summary'])
            self.assertEqual(json.loads((folder/'summary.json').read_text())['status'],'hosting_failed')

    def test_failed_export_read_is_visible_without_success(self):
        tree=ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
        function=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_saved_result'))
        with tempfile.TemporaryDirectory() as temp:
            artifacts=Path(temp);folder=artifacts/'synthetix_fixture';folder.mkdir()
            source=folder/'..'/folder.name/'version_0.html';source.write_text('<html>Original</html>')
            (folder/'summary.json').write_text(json.dumps({'status':'diagnosis_only'}))
            script='''
import streamlit as st
from pathlib import Path
import json
from workspace_ui import render_workspace
def perform_job(job):raise AssertionError('No worker should run')
def preview_document(*args):pass
pages={}
st.session_state['run_folder']='''+repr(str(folder))+"\n"+function+'\nrender_saved_result()\n'
            original_read=Path.read_bytes
            attempted=[]
            canonical_source=source.resolve()
            def guarded(path):
                if path.resolve()==canonical_source:
                    attempted.append(path)
                    raise PermissionError('audit export read failure')
                return original_read(path)
            with patch.object(project_store,'ARTIFACTS',artifacts),patch.object(Path,'read_bytes',guarded):
                app=AppTest.from_string(script).run()
            self.assertTrue(attempted,'The simulated failure must target the resolved export path')
            self.assertFalse(app.exception)
            self.assertTrue(any('audit export read failure' in error.value for error in app.error))
            self.assertEqual(len(app.success),0)
