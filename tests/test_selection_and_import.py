import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import project_store,ui_worker,web_documents

ROOT=Path(web_documents.__file__).parent


class SavedSelectionTests(unittest.TestCase):
    def fixture(self,root):
        folder=root/'synthetix_fixture';folder.mkdir()
        (folder/'version_0.html').write_text('<html><body>Original</body></html>')
        (folder/'summary.json').write_text(json.dumps({'status':'no_runtime_errors_observed','intent_checks_verified':True,'intent_check_steps':1}))
        return folder

    def test_missing_approved_steps_cannot_silently_become_runtime_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=self.fixture(root)
            clean={'javascript_errors':[],'console_errors':[],'combined_errors':{'javascript_errors':[],'console_errors':[],'behavior_errors':[],'execution_errors':[]}}
            with patch.object(project_store,'ARTIFACTS',root),patch.object(ui_worker,'ARTIFACTS',root),patch.object(ui_worker,'check_version',return_value=clean):
                with self.assertRaisesRegex(ValueError,'selection|checks|steps'):ui_worker.handle({'workflow':'test_saved','output_folder':str(folder),'version':'version_0.html'})

    def test_restore_never_discards_a_missing_approved_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=self.fixture(root)
            with patch.object(project_store,'ARTIFACTS',root):
                with self.assertRaisesRegex(ValueError,'selection|checks|steps'):project_store.restore_version(folder,'version_0.html')
            self.assertEqual((folder/'version_0.html').read_text(),'<html><body>Original</body></html>')

    def test_restore_preserves_crlf_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=self.fixture(root)
            (folder/'run.json').write_text(json.dumps({'intent_checks':[{'action':'expect_text','by':'css','selector':'body','text':'Original'}]}))
            original=b'<!DOCTYPE html>\r\n<html>\r\n<body>Original</body></html>\r\n'
            (folder/'version_0.html').write_bytes(original)
            with patch.object(project_store,'ARTIFACTS',root):draft=project_store.restore_version(folder,'version_0.html')
            self.assertEqual((draft/'version_0.html').read_bytes(),original)


class UploadIdentityTests(unittest.TestCase):
    def test_reuploading_same_file_after_edits_reimports_it(self):
        tree=ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
        source=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='code_editor'))
        script='''
import streamlit as st
from text_safety import markdown_text
import hashlib
class Uploaded:
    def __init__(self,identity):self.file_id=identity
    def getvalue(self):return b'<html>Uploaded source A</html>'
if 'fixture_upload_id' not in st.session_state:st.session_state['fixture_upload_id']='first'
st.file_uploader=lambda *args,**kwargs:Uploaded(st.session_state['fixture_upload_id'])
'''+source+"\ncode_editor('repair')\n"
        app=AppTest.from_string(script).run()
        self.assertFalse(app.exception)
        app.text_area(key='repair_html').set_value('<html>Edited source B</html>').run()
        self.assertEqual(app.text_area(key='repair_html').value,'<html>Edited source B</html>')
        app.session_state['fixture_upload_id']='second'
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key='repair_html').value,'<html>Uploaded source A</html>')
