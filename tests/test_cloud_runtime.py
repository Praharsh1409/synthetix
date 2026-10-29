from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import runtime_paths as runtime
import design_interview
import project_store
import hosting
import browser_safety


class CloudRuntimeTests(unittest.TestCase):
    def test_local_paths_and_environment_are_preserved(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(runtime.cloud_mode())
            self.assertEqual(runtime.artifacts_dir(Path('local')), Path('local'))
            self.assertEqual(runtime.worker_environment({'NEBIUS_API_KEY':'local-key'})['NEBIUS_API_KEY'], 'local-key')

    def test_invalid_identifiers_fail_closed(self):
        for value in ('../other', 'a'*32, 'A'*64, '', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                with runtime.visitor_workspace(value):
                    pass

    def test_visitor_paths_do_not_cross_threads(self):
        barrier = threading.Barrier(2)
        def work(identifier):
            with runtime.visitor_workspace(identifier):
                barrier.wait()
                return runtime.session_id(), runtime.artifacts_dir()
        with ThreadPoolExecutor(2) as pool:
            first=pool.submit(work, 'a'*64)
            second=pool.submit(work, 'b'*64)
            a,b=first.result(),second.result()
        self.assertEqual(a[0], 'a'*64)
        self.assertEqual(b[0], 'b'*64)
        self.assertNotEqual(a[1], b[1])
        self.assertIsNone(runtime.session_id())

    def test_interview_and_run_access_are_scoped(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runtime, 'ROOT', Path(temporary)):
            with runtime.visitor_workspace('a'*64):
                state=design_interview.create('A private learning website')
                folder=runtime.artifacts_dir()/'synthetix_private'
                folder.mkdir()
                self.assertEqual(design_interview.load(state['id'])['id'],state['id'])
                self.assertEqual(project_store.safe_run(folder),folder.resolve())
            with runtime.visitor_workspace('b'*64):
                self.assertEqual(design_interview.list_interviews(), [])
                with self.assertRaises((OSError,ValueError)):
                    design_interview.load(state['id'])
                with self.assertRaises(ValueError):
                    project_store.safe_run(folder)

    def test_owner_key_is_not_inherited_by_visitors(self):
        with runtime.visitor_workspace('a'*64):
            environment=runtime.worker_environment({'NEBIUS_API_KEY':'owner-secret'})
            self.assertNotIn('NEBIUS_API_KEY',environment)
            environment=runtime.worker_environment({'NEBIUS_API_KEY':'owner-secret'},' visitor-secret ')
            self.assertEqual(environment['NEBIUS_API_KEY'],'visitor-secret')
            self.assertEqual(environment['SYNTHETIX_CLOUD_SESSION'],'a'*64)
            with patch.dict(os.environ,environment,clear=True):
                self.assertNotIn('NEBIUS_API_KEY',browser_safety.browser_environment())
                self.assertNotIn('SYNTHETIX_CLOUD_SESSION',browser_safety.browser_environment())

    def test_online_hosting_does_not_start_a_localhost_server(self):
        with runtime.visitor_workspace('a'*64), patch.object(hosting,'ensure_host',side_effect=AssertionError('No local port')):
            site=hosting.publish_html('<html><p>Original code</p></html>')
            self.assertEqual(site['mode'],'browser_preview')
            self.assertNotIn('url',site)
            self.assertFalse(site['http_verified'])
            self.assertIsNone(hosting.running_host())

    def test_global_worker_limit_is_released_after_failure(self):
        with runtime.visitor_workspace('a'*64):
            with runtime.job_slot():
                with self.assertRaisesRegex(ValueError,'Another visitor'):
                    with runtime.job_slot():
                        pass
            with self.assertRaisesRegex(RuntimeError,'test failure'):
                with runtime.job_slot():
                    raise RuntimeError('test failure')
            with runtime.job_slot():
                pass

    def test_model_key_only_required_for_ai_workflows(self):
        for workflow in ('diagnose','test_saved','host_code','host_existing'):
            self.assertFalse(runtime.requires_model({'workflow':workflow}))
        for workflow in ('interview_turn','interview_build','repair','demo'):
            self.assertTrue(runtime.requires_model({'workflow':workflow}))

    def test_cloud_entry_has_private_key_input_and_no_shared_history(self):
        app=AppTest.from_file(str(runtime.ROOT/'cloud_app.py')).run(timeout=20)
        self.assertFalse(app.exception)
        key=app.text_input(key='visitor_nebius_key')
        self.assertEqual(key.value,'')
        self.assertEqual(len(app.session_state['cloud_workspace_id']),64)
        self.assertTrue(any('Temporary visitor workspace' in item.value for item in app.caption))

    def test_cloud_worker_rejects_missing_key_before_saving_request(self):
        script='''
import streamlit as st
from runtime_paths import visitor_workspace
import runpy
with visitor_workspace('c'*64):
    app = runpy.run_path('app.py', run_name='test_app')
    result = app['execute_job']({'workflow':'generate','prompt':'A page'},None)
    st.json(result)
'''
        app=AppTest.from_string(script).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertFalse(json.loads(app.json[-1].value)['ok'])
        self.assertIn('Add your Nebius API key',json.loads(app.json[-1].value)['error'])

    def test_visitor_key_survives_navigation_to_build(self):
        app=AppTest.from_file(str(runtime.ROOT/'cloud_app.py')).run(timeout=20)
        app.text_input(key='visitor_nebius_key').set_value('test-only-visitor-key').run()
        next(button for button in app.button if button.label=='New project').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['visitor_nebius_key'],'test-only-visitor-key')
        # A further rerun must not clear the key after navigation completes.
        app.run()
        self.assertEqual(app.session_state['visitor_nebius_key'],'test-only-visitor-key')
