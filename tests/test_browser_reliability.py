import time
import unittest
from intent_checks import check_intent, validate_checks


class BehaviourReliabilityTests(unittest.TestCase):
    def test_non_string_model_actions_and_locators_are_validation_errors(self):
        for key in ('action', 'by'):
            for invalid in ({'nested': 'css'}, ['css'], None, 1):
                step = {'action':'expect_text', 'by':'css', 'selector':'#count', 'text':'0'}
                step[key] = invalid
                with self.subTest(key=key, invalid=invalid):
                    with self.assertRaises(ValueError):
                        validate_checks([step])

    def test_hidden_text_is_not_a_user_visible_pass(self):
        result=check_intent('<output id="count" hidden>1</output><p>Visible: 999</p>',[
            {'action':'expect_text','by':'css','selector':'#count','text':'1'}])
        self.assertFalse(result['passed'])
        self.assertTrue(result['behavior_errors'])

    def test_hidden_value_is_not_a_user_visible_pass(self):
        result=check_intent('<input id="value" type="hidden" value="correct">',[
            {'action':'expect_value','by':'css','selector':'#value','value':'correct'}])
        self.assertFalse(result['passed'])

    def test_action_only_plan_needs_an_assertion(self):
        with self.assertRaisesRegex(ValueError,'assertion'):
            validate_checks([{'action':'click','by':'css','selector':'#button'}])

    def test_delayed_interaction_exception_is_observed(self):
        source='<button id="go" onclick="document.getElementById(\'value\').textContent=\'1\';setTimeout(()=>{throw new Error(\'delayed interaction failure\')},100)">Go</button><output id="value">0</output>'
        checks=[{'action':'click','by':'css','selector':'#go'},
                {'action':'expect_text','by':'css','selector':'#value','text':'1'}]
        result=check_intent(source,checks)
        self.assertFalse(result['passed'])
        self.assertTrue(any('delayed interaction failure' in message for message in result['javascript_errors']))

    def test_later_steps_are_explicitly_unexecuted(self):
        checks=[{'action':'expect_text','by':'css','selector':'#value','text':'1'},
                {'action':'expect_visible','by':'css','selector':'#button'}]
        result=check_intent('<p id="value">wrong</p><button id="button">Unused</button>',checks)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result.get('checks_not_run',[])),1)

    def test_checks_are_isolated_between_runs(self):
        source='<output id="value">0</output>'
        checks=[{'action':'expect_text','by':'css','selector':'#value','text':'0'}]
        self.assertTrue(check_intent(source,checks)['passed'])
        self.assertTrue(check_intent(source,checks)['passed'])
