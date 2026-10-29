from copy import deepcopy
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import design_interview as d
import design_refinement as polish
import guided_interview as guided
import ui_worker
import synthetix


def complete(state):
    state=deepcopy(state)
    state.update(pending=False, questions=[])
    state=d.update_requirements(state,{
        'purpose':'Help students plan study tasks', 'audience':'Students', 'goals':'Add and complete tasks',
        'pages':'One task-planner page', 'functionality':'Add, complete, delete and filter tasks. Progress is calculated from all tasks.',
        'theme':'Dark', 'palette':'Navy, white and coral', 'layout':'Bento layout with a task list and progress panel',
    })
    return guided.select_styles(state,['Bento UI','Minimalism'])


def plan(state):
    return {
        'anchors': {key:state['requirements'][key]['value'] for key in polish.ANCHORS},
        'concept':'A focused study desk: tasks lead, with a compact progress strip.',
        'composition':'Use a wide task panel beside a compact progress panel. Stack them on phones.',
        'typography':'Use a readable system sans-serif, 30px title and 16px task text.',
        'surfaces':'Navy background, quieter dark surfaces, white text and coral on the primary action.',
        'signature_detail':'Use a small inline notebook motif in the empty state, without fake tasks or data.',
        'motion':[{'trigger':'A task is added','effect':'Fade and lift only the new row by 6px','duration_ms':180},
                  {'trigger':'Completion changes','effect':'Transition the progress fill without delaying the number','duration_ms':280}],
    }


class DesignRefinementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=patch.object(d,'STORE',Path(self.temp.name)/'interviews')
        self.store.start()
        self.state=complete(d.create('StudySprint, a student task planner'))

    def tearDown(self):
        self.store.stop()
        self.temp.cleanup()

    def test_refinement_is_a_real_model_proposal_without_changing_requirements(self):
        calls=[]
        def ask(system,user):
            calls.append((system,json.loads(user)))
            return plan(self.state)
        refined=polish.refine(self.state,ask=ask)
        self.assertEqual(len(calls),1)
        self.assertEqual(d.requirement_values(refined),d.requirement_values(self.state))
        self.assertEqual(calls[0][1]['requirements']['functionality'],d.requirement_values(self.state)['functionality'])
        self.assertIsNone(refined['approved_brief'])
        self.assertIn('Fade and lift only the new row',d.render_brief(refined))
        self.assertIn('prefers-reduced-motion',d.render_brief(refined))

    def test_model_cannot_change_style_theme_or_palette(self):
        for field in polish.ANCHORS:
            value=plan(self.state)
            value['anchors'][field]='A different choice'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'changed your selected'):
                polish.refine(self.state,ask=lambda *_:value)

    def test_invalid_design_schema_has_one_bounded_correction(self):
        calls=[]
        def ask(system,user):
            calls.append(system)
            return {'design':plan(self.state)} if len(calls)==1 else plan(self.state)
        self.assertEqual(polish.current(polish.refine(self.state,ask=ask))['status'],'ready')
        self.assertEqual(len(calls),2)
        self.assertIn('Correct the JSON schema',calls[1])
        calls.clear()
        def broken(*args):calls.append(1);return {}
        with self.assertRaises(ValueError):polish.refine(self.state,ask=broken)
        self.assertEqual(len(calls),2)

    def test_invalid_or_excessive_motion_and_unknown_fields_are_rejected(self):
        for duration in (-1,0,True,601,'180'):
            value=plan(self.state);value['motion'][0]['duration_ms']=duration
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                polish.validate_plan(value,self.state)
        value=plan(self.state);value['new_features']=['Login']
        with self.assertRaises(ValueError):polish.validate_plan(value,self.state)
        value=plan(self.state);value['motion']*=2
        with self.assertRaises(ValueError):polish.validate_plan(value,self.state)

    def test_explicit_no_motion_preference_wins(self):
        state=d.update_requirements(self.state,{'interactions':'No animations. Keep state changes immediate.'})
        self.assertFalse(polish.motion_allowed(state))
        with self.assertRaises(ValueError):polish.validate_plan(plan(state),state)
        value=plan(state);value['motion']=[]
        refined=polish.refine(state,ask=lambda *_:value)
        self.assertIn('Motion: no animated entrances',d.render_brief(refined))

    def test_requirement_changes_cannot_reuse_a_stale_design_plan(self):
        refined=polish.refine(self.state,ask=lambda *_:plan(self.state))
        changed=d.update_requirements(refined,{'palette':'White and green'})
        self.assertIsNone(polish.current(changed))
        self.assertNotIn('A focused study desk',d.render_brief(changed))

    def test_concrete_bento_structure_is_only_added_for_selected_bento_style(self):
        self.assertIn('CSS foundation:',polish.generation_guidance(d.render_brief(self.state)))
        state=d.update_requirements(self.state,{'selected_styles':'Editorial Design'})
        self.assertNotIn('CSS foundation:',polish.generation_guidance(d.render_brief(state)))
        self.assertIn('StudySprint, a student task planner',d.render_brief(state))

    def test_legacy_console_cannot_turn_a_passing_browser_check_into_a_failure(self):
        errors={key:[] for key in ('javascript_errors','console_errors','behavior_errors','execution_errors')}
        evidence={**errors,'passed':True,'checks_passed':['Progress 0 \u2192 50%']}
        output=io.TextIOWrapper(io.BytesIO(),encoding='cp1252',errors='strict')
        with patch.object(synthetix,'check_html',return_value=errors),patch.object(synthetix,'check_intent',return_value=evidence),patch('sys.stdout',output):
            result=synthetix.check_version('<html></html>','unused.png',intent_checks=[{'action':'expect_text','by':'css','selector':'#progress','text':'50%'}])
        self.assertTrue(result['passed'])

    def test_generation_uses_the_exact_approved_polished_brief(self):
        refined=polish.refine(self.state,ask=lambda *_:plan(self.state))
        approved=guided.approve(refined,d.render_brief(refined)+'\nKeep the footer compact.')
        prompt,context=d.build_spec(approved)
        self.assertEqual(prompt,approved['approved_brief']['text'])
        self.assertEqual(context['approved_brief'],prompt)
        self.assertIn('A focused study desk',prompt)
        self.assertIn('Keep the footer compact',prompt)

    def test_refine_again_requires_fresh_approval_and_skip_restores_original(self):
        approved=guided.approve(self.state,d.render_brief(self.state))
        refined=polish.refine(approved,ask=lambda *_:plan(approved))
        with self.assertRaises(ValueError):d.build_spec(refined)
        skipped=polish.skip(refined)
        self.assertEqual(polish.current(skipped)['status'],'skipped')
        self.assertNotIn('Visual execution plan',d.render_brief(skipped))
        self.assertEqual(d.requirement_values(skipped),d.requirement_values(self.state))

    def test_worker_retains_model_failure_without_overwriting_requirements(self):
        state=d.save(self.state,expected_revision=self.state['revision'])
        with patch.object(polish,'refine',side_effect=RuntimeError('Model unavailable')):
            result=ui_worker.handle({'workflow':'interview_refine','interview_id':state['id'],'revision':state['revision']})
        self.assertFalse(result['ok'])
        saved=d.load(state['id'])
        self.assertEqual(polish.current(saved)['status'],'failed')
        self.assertEqual(d.requirement_values(saved),d.requirement_values(state))

    def test_worker_rejects_stale_refinement_before_calling_model(self):
        state=d.save(self.state,expected_revision=self.state['revision'])
        with patch.object(polish,'refine') as refine:
            with self.assertRaises(ValueError):
                ui_worker.handle({'workflow':'interview_refine','interview_id':state['id'],'revision':state['revision']-1})
            refine.assert_not_called()

    def test_automatic_refinement_runs_once_and_original_brief_remains_available(self):
        state=d.save(self.state,expected_revision=self.state['revision'])
        script=f'''
import streamlit as st
import design_interview as d
from interview_ui import render_final
def blocked(job):
    st.session_state['calls']=st.session_state.get('calls',0)+1
    return {{'ok':False,'error':'Add your API key'}}
render_final(d.load({state['id']!r}),blocked)
'''
        app=AppTest.from_string(script,default_timeout=15).run()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['calls'],1)
        self.assertEqual(polish.current(d.load(state['id']))['status'],'failed')
        self.assertTrue(any(area.label=='Editable design brief' for area in app.text_area))

    def test_saved_interview_without_new_flag_does_not_make_an_automatic_request(self):
        state=deepcopy(self.state);state.pop('auto_design_refinement',None)
        state=d.save(state,expected_revision=self.state['revision'])
        script=f"from interview_ui import render_final\nimport design_interview as d\ndef no_request(job):raise AssertionError('Unexpected AI request')\nrender_final(d.load({state['id']!r}),no_request)"
        app=AppTest.from_string(script,default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertTrue(any(button.label=='Refine the design with AI' for button in app.button))
