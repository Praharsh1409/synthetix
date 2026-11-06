import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime_paths as runtime
import ui_worker

CODE='<!doctype html><html><body><button id="add">Add</button><output id="value">0</output><script>let n=0;add.onclick=()=>{value.textContent=++n}</script></body></html>'
CHECKS=[{'action':'click','by':'role','role':'button','name':'Add'},
        {'action':'expect_text','by':'css','selector':'#value','text':'1'}]


def report(failed=False):
    errors={key:[] for key in ('javascript_errors','console_errors','behavior_errors','execution_errors')}
    if failed:errors['behavior_errors']=[{'step':'Count','details':'Expected one'}]
    return {**errors,'combined_errors':errors,'passed':not failed}


class ManualCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=patch.object(runtime,'ROOT',Path(self.temp.name));self.root.start();self.addCleanup(self.root.stop)
        self.visitor=runtime.visitor_workspace('a'*64);self.visitor.__enter__();self.addCleanup(self.visitor.__exit__,None,None,None)
        self.folder=runtime.artifacts_dir()/'synthetix_diagnosis_fixture';self.folder.mkdir(parents=True)
        (self.folder/'version_0.html').write_bytes(CODE.encode())
        (self.folder/'diagnosis.json').write_text(json.dumps({'code_hash':hashlib.sha256(CODE.encode()).hexdigest()}))
        self.request={'workflow':'test_imported','diagnosis_folder':str(self.folder),'intent_checks':CHECKS,'checks_reviewed':True}

    def test_approval_required_before_browser_execution(self):
        self.request['checks_reviewed']=False
        with patch.object(ui_worker,'check_version') as browser,self.assertRaisesRegex(ValueError,'approve'):
            ui_worker.handle(self.request)
        browser.assert_not_called()

    def test_changed_source_requires_new_inspection(self):
        (self.folder/'version_0.html').write_text(CODE+' ')
        with patch.object(ui_worker,'check_version') as browser,self.assertRaisesRegex(ValueError,'source changed'):
            ui_worker.handle(self.request)
        browser.assert_not_called()

    def test_approved_checks_are_saved_and_rerun_without_modifying_source(self):
        with patch.object(ui_worker,'check_version',return_value=report()) as browser,patch.object(ui_worker,'run_pipeline',side_effect=AssertionError('No AI')):
            result=ui_worker.handle(self.request)
            self.assertTrue(result['ok']);self.assertTrue(result['summary']['intent_checks_verified'])
            folder=Path(result['output_folder'])
            self.assertEqual((folder/'version_0.html').read_bytes(),CODE.encode())
            self.assertEqual((self.folder/'version_0.html').read_bytes(),CODE.encode())
            self.assertEqual(json.loads((folder/'run.json').read_text())['intent_checks'],CHECKS)
            rerun=ui_worker.handle({'workflow':'test_saved','output_folder':str(folder),'version':'version_0.html'})
            self.assertTrue(rerun['ok'])
            self.assertEqual(browser.call_args.args[3],CHECKS)

    def test_failed_checks_preserve_source_and_honest_outcome(self):
        with patch.object(ui_worker,'check_version',return_value=report(True)),patch.object(ui_worker,'run_pipeline',side_effect=AssertionError('No AI')):
            result=ui_worker.handle(self.request)
        self.assertFalse(result['ok']);self.assertFalse(result['summary']['intent_checks_verified'])
        self.assertEqual(result['summary']['status'],'checks_failed')
        folder=Path(result['output_folder'])
        self.assertFalse((folder/'final.html').exists())
        self.assertEqual((folder/'version_0.html').read_bytes(),CODE.encode())
