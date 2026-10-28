import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import synthetix
import project_store
from artifact_io import write_text
from web_documents import assemble_document
from nebius_tasks import plan_repair


def runtime(*errors):
    return {'javascript_errors':list(errors),'console_errors':[],'execution_errors':[]}


class PipelineHistoryTests(unittest.TestCase):
    def test_model_repair_failure_keeps_original_and_discoverable_failure(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(synthetix,'PROJECT_FOLDER',Path(temp)), patch.object(synthetix,'check_html',return_value=runtime('seeded failure')), patch.object(synthetix,'repair_html',side_effect=TimeoutError('model timed out')):
            original='<!DOCTYPE html>\n<html>Original source</html>\n'
            try:result=synthetix.run_pipeline('Audit repair',initial_html=original)
            except TimeoutError:result={}
            folder=next((Path(temp)/'artifacts').iterdir())
            self.assertTrue((folder/'summary.json').exists())
            self.assertEqual(result.get('status'),'repair_failed')
            self.assertEqual((folder/'version_0.html').read_bytes(),original.encode())
            self.assertTrue((folder/'report_0.json').exists())
            self.assertFalse((folder/'final.html').exists())

    def test_generation_failure_is_a_saved_failed_run(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(synthetix,'PROJECT_FOLDER',Path(temp)), patch.object(synthetix,'generate_html',side_effect=RuntimeError('service unavailable')):
            try:result=synthetix.run_pipeline('Audit generation')
            except RuntimeError:result={}
            self.assertEqual(result.get('status'),'generation_failed')
            folder=next((Path(temp)/'artifacts').iterdir())
            self.assertEqual(json.loads((folder/'summary.json').read_text())['status'],'generation_failed')

    def test_same_checks_retest_after_repair_and_catch_new_runtime_failure(self):
        checks=[{'action':'expect_text','by':'css','selector':'#value','text':'1'}]
        failed={'passed':False,'checks_passed':[],'javascript_errors':[],'console_errors':[],
                'behavior_errors':[{'step':'Value is one','details':'Observed 2'}]}
        passed={'passed':True,'checks_passed':['Value is one'],'javascript_errors':[],'console_errors':[],'behavior_errors':[]}
        with tempfile.TemporaryDirectory() as temp, patch.object(synthetix,'PROJECT_FOLDER',Path(temp)), patch.object(synthetix,'check_html',side_effect=[runtime(),runtime('new failure'),runtime()]), patch.object(synthetix,'check_intent',side_effect=[failed,passed]) as tester, patch.object(synthetix,'repair_html',side_effect=['<html>new failure</html>','<html>fixed</html>']):
            result=synthetix.run_pipeline('Audit repair',initial_html='<html>original</html>',intent_checks=checks)
            self.assertEqual(result['status'],'no_runtime_errors_observed')
            self.assertEqual(result['repairs_used'],2)
            self.assertEqual([call.args[1] for call in tester.call_args_list],[checks,checks])
            report=json.loads((Path(result['output_folder'])/'report_1.json').read_text())
            self.assertTrue(report['intent_check']['skipped'])
            self.assertTrue(report['combined_errors']['javascript_errors'])
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'],'failed')

    def test_repair_limit_never_creates_a_passing_final(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(synthetix,'PROJECT_FOLDER',Path(temp)), patch.object(synthetix,'check_html',return_value=runtime('still broken')), patch.object(synthetix,'repair_html',return_value='<html>still broken</html>') as repair:
            result=synthetix.run_pipeline('Audit repair cap',initial_html='<html>original</html>')
            self.assertEqual(result['status'],'repair_limit_reached')
            self.assertEqual(repair.call_count,3)
            self.assertFalse((Path(result['output_folder'])/'final.html').exists())

    def test_execution_failure_cannot_be_reported_as_pass(self):
        report={**runtime(),'execution_errors':['Browser launch failed']}
        with tempfile.TemporaryDirectory() as temp, patch.object(synthetix,'PROJECT_FOLDER',Path(temp)), patch.object(synthetix,'check_html',return_value=report), patch.object(synthetix,'repair_html') as repair:
            result=synthetix.run_pipeline('Audit infrastructure',initial_html='<html>original</html>')
            self.assertEqual(result['status'],'execution_failed')
            self.assertFalse((Path(result['output_folder'])/'final.html').exists())
            repair.assert_not_called()


class ImportAndStorageTests(unittest.TestCase):
    def test_malformed_html_does_not_drop_separate_javascript(self):
        result=assemble_document('<html><head></head><p>Unclosed body','','window.auditFlag=true;')
        self.assertIn('window.auditFlag=true;',result)

    def test_complete_source_without_additions_is_preserved(self):
        source='\n<html><head></head><body>Original</body></html>\n'
        self.assertEqual(assemble_document(source),source)

    def test_atomic_failure_does_not_destroy_saved_source(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'version.html';file.write_bytes(b'original')
            with patch.object(Path,'replace',side_effect=PermissionError('seeded write failure')):
                with self.assertRaises(PermissionError):write_text(file,'replacement')
            self.assertEqual(file.read_bytes(),b'original')
            self.assertEqual(list(Path(temp).glob('*.tmp')),[])

    def test_nonobject_json_never_crashes_saved_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'synthetix_fixture';folder.mkdir()
            (folder/'summary.json').write_text('[]')
            with patch.object(project_store,'ARTIFACTS',root):
                info=project_store.describe_run(folder)
                self.assertNotEqual(info['status'],'no_runtime_errors_observed')

    def test_missing_model_checks_is_rejected_instead_of_crashing_ui(self):
        invalid={'understanding':'Counter','likely_issues':[],'assumptions':[]}
        with patch('nebius_tasks.ask_json',return_value=invalid):
            with self.assertRaises(ValueError):plan_repair('<p>Counter</p>','Increase by one',{})
