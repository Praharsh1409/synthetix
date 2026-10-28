import ast
import hashlib
import json
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
import web_documents

ROOT=Path(web_documents.__file__).parent


class TrustInterfaceTests(unittest.TestCase):
    def test_editing_approved_checks_requires_fresh_approval(self):
        tree=ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
        source=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_workflow'))
        script='''
import streamlit as st
from text_safety import markdown_text
import hashlib,json
from intent_checks import validate_checks,describe_check
from web_documents import assemble_document
CODE='<html><output id="value">0</output></html>'
PURPOSE='Counter increases by one'
checks=[{'action':'expect_text','by':'css','selector':'#value','text':'1'}]
def code_editor(prefix):return {'html':CODE,'css':'','javascript':''}
def perform_job(job):raise AssertionError('No model operation is allowed in this UI fixture')
if 'fixture_ready' not in st.session_state:
    st.session_state['fixture_ready']=True
    digest=hashlib.sha256(assemble_document(CODE).encode()).hexdigest()
    st.session_state['diagnosis']={'folder':'test-only','code_hash':digest,'report':{'combined_errors':{}}}
    st.session_state['repair_purpose']=PURPOSE
    st.session_state['repair_plan']={'understanding':PURPOSE,'checks':checks}
    st.session_state['repair_plan_signature']=hashlib.sha256((digest+PURPOSE).encode()).hexdigest()
    st.session_state['approved_checks_json']=json.dumps(checks)
'''+source+"\nrender_workflow('Repair code')\n"
        app=AppTest.from_string(script).run()
        self.assertFalse(app.exception)
        app.checkbox[0].set_value(True).run()
        self.assertTrue(app.checkbox[0].value)
        changed=[{'action':'expect_text','by':'css','selector':'#value','text':'2'}]
        app.text_area(key='approved_checks_json').set_value(json.dumps(changed)).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.checkbox[0].value,'Approval persisted for a different test plan')
        self.assertTrue(any('value' in item.value and '2' in item.value for item in app.markdown),'The visible approval list still describes the original model checks')
        self.assertTrue(next(button for button in app.button if button.label=='Repair, verify and host locally').disabled)

    def test_incomplete_report_does_not_display_runtime_pass(self):
        app=AppTest.from_string("from workspace_ui import diagnostics\ndiagnostics({'combined_errors':{}})").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.success),0)

    def test_execution_error_does_not_display_runtime_pass(self):
        report={'javascript_errors':[],'console_errors':[],'execution_errors':['Browser could not run']}
        app=AppTest.from_string('from workspace_ui import diagnostics\ndiagnostics('+repr(report)+')').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.success),0)
