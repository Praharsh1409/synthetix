import unittest
from streamlit.testing.v1 import AppTest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PaperWorkbenchTests(unittest.TestCase):
    def test_starter_and_draft_survive_navigation(self):
        app = AppTest.from_file(str(ROOT/'cloud_app.py')).run(timeout=20)
        next(b for b in app.button if b.label=='Photographer portfolio').click().run()
        idea = app.text_area(key='studio_idea').value
        self.assertIn('photographer', idea)
        next(b for b in app.button if b.label=='Start this project ↗').click().run()
        self.assertEqual(app.text_area(key='planning_idea').value, idea)
        self.assertFalse(app.exception)
        self.assertFalse(list((ROOT/'artifacts'/'visitors'/app.session_state['cloud_workspace_id']).glob('ui_jobs/*/request.json')))

    def test_long_failure_evidence_is_not_a_success(self):
        report = {'javascript_errors':['LongError: '+('unexpected_token_'*700)], 'console_errors':[], 'behavior_errors':[], 'execution_errors':[]}
        app=AppTest.from_string('from workspace_ui import diagnostics\ndiagnostics('+repr(report)+')').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertFalse(app.success)

    def test_empty_report_is_not_a_pass(self):
        app=AppTest.from_string('from workspace_ui import diagnostics\ndiagnostics({})').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.success)
        self.assertTrue(app.info)
