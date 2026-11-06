import os
import unittest
from unittest.mock import patch
import ai_backend
import ai_tasks
import generate_ui
import repair_test
import synthetix
from credential_safety import without_credentials
from runtime_paths import worker_environment, visitor_workspace


class AIAvailabilityTests(unittest.TestCase):
    def test_all_model_entry_points_fail_before_network_access(self):
        calls=(lambda:ai_backend.request_completion(messages=[],max_tokens=20),
               lambda:generate_ui.generate_html('A portfolio'),
               lambda:synthetix.repair_html('A page','<!doctype html><html></html>',{}),
               lambda:repair_test.request_repair('<html></html>',{}),
               lambda:ai_tasks.ask_json('Plan','A portfolio'))
        with patch.dict(os.environ,{'EXAMPLE_API_KEY':'not-a-real-secret'}),patch('socket.socket',side_effect=AssertionError('No network')):
            self.assertFalse(ai_backend.available())
            for call in calls:
                with self.subTest(call=call),self.assertRaises(ai_backend.AIUnavailableError):call()

    def test_child_processes_do_not_inherit_credentials(self):
        env={'PATH':'path','SYSTEMROOT':'root','EXAMPLE_API_KEY':'key','SESSION_TOKEN':'token',
             'AWS_SECRET_ACCESS_KEY':'secret','APP_PASSWORD':'password','HTTP_AUTHORIZATION':'authorization'}
        self.assertEqual(without_credentials(env),{'PATH':'path','SYSTEMROOT':'root'})
        self.assertNotIn('EXAMPLE_API_KEY',worker_environment(env))
        with visitor_workspace('a'*64):
            result=worker_environment(env)
            self.assertEqual(result['SYNTHETIX_CLOUD_SESSION'],'a'*64)
            self.assertNotIn('SESSION_TOKEN',result)

    def test_unavailable_message_names_working_alternatives(self):
        for action in ('Import HTML','browser checks','download'):
            self.assertIn(action,ai_backend.UNAVAILABLE_MESSAGE)
