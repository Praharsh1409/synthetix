import tempfile
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

class EditorDraftTests(unittest.TestCase):
    def test_switching_layout_keeps_draft_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'version_0.html'
            source.write_text('<html><h1>Original</h1></html>',encoding='utf-8')
            script='''
import streamlit as st
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from workspace_ui import render_workspace
folder=Path(FOLDER)
item={'folder':folder,'summary':{},'versions':[folder/'version_0.html'],'manifest':{},'title':'Draft fixture','mode':'Inspect','created':datetime(2026,1,1),'status':'diagnosis_only'}
with patch('workspace_ui.describe_run',return_value=item),patch('workspace_ui.running_host',return_value=None):
    render_workspace(folder,lambda job: {},lambda document,title: None,{})
'''.replace('FOLDER',repr(directory))
            app=AppTest.from_string(script).run()
            self.assertFalse(app.exception)
            draft='<html><h1>Edited session draft</h1></html>'
            app.text_area[0].set_value(draft).run()
            next(v for v in app.selectbox if v.label=='Panel layout').select('Preview focus').run()
            next(v for v in app.selectbox if v.label=='Panel layout').select('Studio workspace').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area[0].value,draft)
            self.assertEqual(source.read_text(encoding='utf-8'),'<html><h1>Original</h1></html>')
