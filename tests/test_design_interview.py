"""Acceptance scenarios and approval/persistence regression tests; no live model credits."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import design_interview as d
from design_styles import STYLES, compatibility, recommend, preview
import ui_worker


def response(updates=None,questions=None,recommendations=None):
    return {'message':'Review these proposals, then choose the direction that fits.', 'updates':updates or {},
            'questions':questions or [],'recommendations':recommendations or []}


def complete(state):
    return d.update_requirements(state,{
      'purpose':'A personal developer portfolio','audience':'Engineering recruiters',
      'goals':'Inspect projects and download my resume','pages':'Introduction, projects, skills, contact information',
      'functionality':'Filter project cards by language; show and close project details without external calls.',
      'selected_styles':'Editorial Design + Minimalism','theme':'Light',
      'palette':'Off-white background, charcoal text and navy links.',
      'typography':'Readable sans-serif with serif project headings.',
      'layout':'Spacious, clear project reading order.'})


class InterviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=patch.object(d,'STORE',Path(self.temp.name)/'interviews');self.store.start()
        self.state=d.create('I want a portfolio but need help choosing the design.')

    def tearDown(self):self.store.stop();self.temp.cleanup()

    def reply(self,updates=None,questions=None,recommendations=None):
        return d.respond(self.state,ask=lambda *_:response(updates,questions,recommendations))

    def test_all_fifteen_styles_are_distinct_and_selectable(self):
        self.assertEqual(len(STYLES),15)
        self.assertEqual(len({preview(name) for name in STYLES}),15)
        for name in STYLES:
            state=d.update_requirements(self.state,{'selected_styles':name})
            self.assertEqual(d.styles(state),[name])
            self.assertTrue(STYLES[name]['explanation'] and STYLES[name]['downside'])

    def test_known_style_is_retained_and_answered_question_not_repeated(self):
        self.state=d.update_requirements(self.state,{'selected_styles':'Brutalism'})
        result=self.reply(questions=[{'field':'selected_styles','text':'Which style?','conflict':False}])
        self.assertEqual(d.styles(result),['Brutalism']);self.assertEqual(result['questions'],[])
        self.assertEqual(recommend(result['requirements'])[0]['name'],'Brutalism')

    def test_vague_beginner_is_not_ready_and_gets_targeted_questions(self):
        state=self.reply(questions=[{'field':'audience','text':'Who should visit?','conflict':False}])
        self.assertIn('Target audience',d.blockers(state))
        with self.assertRaises(ValueError):d.confirm_summary(state)
        with self.assertRaises(ValueError):d.build_spec(state)

    def test_choose_everything_creates_proposals_not_approval(self):
        state=self.reply(updates={'selected_styles':'Bento UI + Minimalism','palette':'Dark navy with readable cyan links.'})
        self.assertEqual(state['requirements']['palette']['status'],'proposed')
        self.assertIsNone(state['summary_approval']);self.assertIsNone(state['approved_brief'])

    def test_disagreement_overrides_ai_recommendation(self):
        state=self.reply(updates={'selected_styles':'Minimalism'})
        state=d.update_requirements(state,{'selected_styles':'Neo-Brutalism'})
        self.assertEqual(d.styles(state),['Neo-Brutalism'])
        self.assertEqual(state['requirements']['selected_styles']['source'],'You')

    def test_minor_change_preserves_other_answers_but_invalidates_approval(self):
        state=d.approve_brief(d.confirm_summary(complete(self.reply())))
        changed=d.update_requirements(state,{'palette':'Cream, black and forest green.'})
        self.assertEqual(changed['requirements']['audience'],state['requirements']['audience'])
        self.assertEqual(changed['style_recheck'],[])
        self.assertIsNone(changed['approved_brief'])

    def test_style_change_only_revisits_inferred_dependent_choices(self):
        state=complete(self.reply())
        state=d.update_requirements(state,{'layout':'An AI-suggested bento grid'},source='AI recommendation accepted by you')
        changed=d.update_requirements(state,{'selected_styles':'Maximalism'})
        self.assertIn('layout',changed['style_recheck'])
        self.assertNotIn('palette',changed['style_recheck'])
        self.assertEqual(changed['requirements']['purpose'],state['requirements']['purpose'])

    def test_compatible_combination_has_no_conflict(self):
        self.assertEqual(compatibility(['Bento UI','Minimalism']),[])
        self.assertEqual(compatibility(['Material Design','Flat Design']),[])
        self.assertEqual(compatibility(['Cyberpunk','Bento UI']),[])

    def test_conflicting_combination_requires_explicit_acknowledgement(self):
        state=complete(self.reply())
        state=d.update_requirements(state,{'selected_styles':'Minimalism + Maximalism'})
        self.assertTrue(compatibility(d.styles(state)))
        with self.assertRaises(ValueError):d.confirm_summary(state)
        state['conflict_ack']=d.digest(d.styles(state))
        self.assertIsNotNone(d.confirm_summary(state)['summary_approval'])

    def test_interruption_and_resume_keep_conversation_and_decisions(self):
        state=d.save(complete(self.state),expected_revision=self.state['revision'])
        loaded=d.load(state['id'])
        self.assertEqual(loaded,state);self.assertTrue(loaded['pending'])
        self.assertEqual(d.list_interviews()[0]['id'],state['id'])

    def test_model_failure_preserves_pending_message_and_supports_retry(self):
        before=deepcopy(self.state)
        with self.assertRaises(ValueError):d.respond(self.state,ask=lambda *_:{'message':'not enough'})
        self.assertEqual(self.state,before)
        failed=d.save(d.record_failure(self.state,RuntimeError('Temporary error')),expected_revision=self.state['revision'])
        self.assertTrue(failed['pending']);self.assertIn('Temporary error',failed['last_error'])
        result=d.respond(failed,ask=lambda *_:response({'audience':'Recruiters'}))
        self.assertFalse(result['pending']);self.assertEqual(result['requirements']['audience']['value'],'Recruiters')

    def test_blank_optional_model_fields_do_not_erase_existing_answers(self):
        self.state=d.update_requirements(self.state,{'audience':'Recruiters'})
        result=self.reply(updates={'branding':'','audience':''})
        self.assertEqual(result['requirements']['audience']['value'],'Recruiters')
        self.assertEqual(result['requirements']['branding']['value'],'')

    def test_critical_ambiguity_blocks_confirmation(self):
        state=complete(self.reply())
        state['questions']=[{'field':'functionality','text':'Should clicking select a plan locally or make an actual purchase?','conflict':True}]
        with self.assertRaises(ValueError):d.confirm_summary(state)
        state=d.update_requirements(state,{'functionality':'Select a plan locally and show the chosen price; no purchase.'})
        self.assertEqual(state['questions'],[])

    def test_recommendations_need_reason_alternatives_and_valid_style(self):
        rec={'field':'palette','value':'Navy and white','reason':'Matches a calm technical audience.',
             'tradeoff':'Less expressive than a warm palette.','alternatives':[{'value':'Cream and charcoal','tradeoff':'Warmer reading experience.'}]}
        state=self.reply(recommendations=[rec]);self.assertEqual(state['recommendations'],[rec])
        broken=deepcopy(rec);broken['alternatives']=[]
        with self.assertRaises(ValueError):self.reply(recommendations=[broken])
        with self.assertRaises(ValueError):self.reply(updates={'selected_styles':'Unknown Style'})

    def test_summary_and_final_brief_have_separate_gates(self):
        state=complete(self.reply());summary=d.confirm_summary(state)
        self.assertIn('Engineering recruiters',summary['draft_brief'])
        with self.assertRaises(ValueError):d.build_spec(summary)
        ready=d.approve_brief(summary);prompt,context=d.build_spec(ready)
        self.assertEqual(prompt,ready['draft_brief']);self.assertEqual(context['approved_brief'],prompt)
        self.assertEqual(context['requirements']['selected_styles'],'Editorial Design + Minimalism')
        self.assertEqual(d.stage(ready),'Ready to generate')

    def test_brief_edit_requires_fresh_approval(self):
        state=d.approve_brief(d.confirm_summary(complete(self.reply())))
        edited=d.edit_brief(state,state['draft_brief']+'\nUse a compact footer.')
        with self.assertRaises(ValueError):d.build_spec(edited)
        tampered=deepcopy(state);tampered['draft_brief']+=' changed'
        with self.assertRaises(ValueError):d.build_spec(tampered)

    def test_stale_revision_cannot_overwrite_newer_decisions(self):
        d.save(complete(self.state),expected_revision=self.state['revision'])
        with self.assertRaisesRegex(ValueError,'another tab'):d.save(self.state,expected_revision=self.state['revision'])

    def test_review_can_confirm_unchanged_decision_to_resolve_ambiguity(self):
        state=complete(self.reply())
        state['questions']=[{'field':'audience','text':'Keep recruiters as the audience?','conflict':True}]
        updated=d.update_requirements(state,{'audience':state['requirements']['audience']['value']})
        self.assertEqual(updated['questions'],[])

    def test_concurrent_saves_do_not_overwrite_newer_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(_):
            try:d.save(self.state,expected_revision=self.state['revision']);return 'saved'
            except ValueError:return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),['saved','stale'])

    def test_malformed_saved_state_is_not_silently_replaced(self):
        path=d.path_for(self.state['id']);path.write_text('[]')
        with self.assertRaises(ValueError):d.load(self.state['id'])
        self.assertEqual(path.read_text(),'[]');self.assertEqual(d.list_interviews(),[])

    def test_incomplete_saved_metadata_and_decisions_are_rejected(self):
        state=deepcopy(self.state);state.pop('updated_at')
        with self.assertRaises(ValueError):d.validate_state(state)
        state=deepcopy(self.state);state['requirements']['purpose'].pop('source')
        with self.assertRaises(ValueError):d.validate_state(state)

    def test_new_message_keeps_history_but_requires_fresh_approval(self):
        state=d.approve_brief(d.confirm_summary(complete(self.reply())))
        changed=d.queue_message(state,'Actually make the typography warmer.')
        self.assertIsNone(changed['approved_brief']);self.assertTrue(changed['pending'])
        self.assertEqual(changed['conversation'][-1]['content'],'Actually make the typography warmer.')

    def test_worker_generates_from_exact_approved_brief(self):
        state=d.save(d.approve_brief(d.confirm_summary(complete(self.reply()))),expected_revision=self.state['revision'])
        with patch.object(ui_worker,'run_pipeline',return_value={'status':'no_runtime_errors_observed','output_folder':'fixture-run'}) as generate,patch.object(ui_worker,'attach_host',side_effect=lambda summary,_:summary):
            result=ui_worker.handle({'workflow':'interview_build','interview_id':state['id'],'revision':state['revision'],'approval_hash':state['approved_brief']['hash'],'prompt':'UNAPPROVED OVERRIDE'})
        self.assertTrue(result['ok'])
        self.assertEqual(generate.call_args.args[0],state['approved_brief']['text'])
        self.assertEqual(generate.call_args.kwargs['workflow_context']['requirements']['audience'],'Engineering recruiters')
        self.assertEqual(len(d.load(state['id'])['build_runs']),1)

    def test_worker_refuses_unapproved_build_before_calling_model(self):
        with patch.object(ui_worker,'run_pipeline') as generate:
            with self.assertRaises(ValueError):ui_worker.handle({'workflow':'interview_build','interview_id':self.state['id'],'revision':self.state['revision']})
            generate.assert_not_called()

    def test_worker_retains_model_failure_for_resume(self):
        with patch.object(d,'respond',side_effect=RuntimeError('Model unavailable')):
            result=ui_worker.handle({'workflow':'interview_turn','interview_id':self.state['id'],'revision':self.state['revision']})
        self.assertFalse(result['ok']);saved=d.load(self.state['id'])
        self.assertTrue(saved['pending']);self.assertIn('Model unavailable',saved['last_error'])

    def test_contextual_ranking_changes_with_project_purpose(self):
        self.assertEqual(recommend({},'A dashboard for developer diagnostics')[0]['name'],'Bento UI')
        self.assertEqual(recommend({},'An editorial magazine with long articles')[0]['name'],'Editorial Design')
        self.assertEqual(recommend({},'A vintage retro game collection')[0]['name'],'Retro Design')

    def test_ui_style_controls_and_approval_lock(self):
        # Real Streamlit widgets over persisted state; no replacement AI conversation.
        identifier=self.state['id']
        code=f'''
import streamlit as st
from interview_ui import render_interview
st.session_state['design_interview_id']={identifier!r}
render_interview(lambda job: None)
'''
        app=AppTest.from_string(code,default_timeout=15).run()
        self.assertFalse(app.exception)
        select=next(w for w in app.multiselect if w.label=='Choose your styles (up to three)')
        self.assertEqual(set(select.options),set(STYLES))
        confirm=next(b for b in app.button if b.label=='Confirm and generate design brief')
        self.assertTrue(confirm.disabled)
        self.assertFalse(any(b.label=='Build, check and host locally' for b in app.button))

    def test_ui_approval_submits_exact_edited_text_and_build_catches_unsaved_edits(self):
        state=d.save(d.confirm_summary(complete(self.reply())),expected_revision=self.state['revision'])
        code=f'''
import streamlit as st
from interview_ui import render_interview
st.session_state['design_interview_id']={state['id']!r}
def no_build(job):raise AssertionError('Unapproved edits must not start generation')
render_interview(no_build)
'''
        app=AppTest.from_string(code,default_timeout=15).run()
        draft=state['draft_brief']+'\nUse a compact footer.'
        next(w for w in app.text_area if w.label=='Editable design brief').set_value(draft)
        app.checkbox[0].check()
        next(b for b in app.button if b.label=='Approve design brief').click().run()
        self.assertFalse(app.exception)
        approved=d.load(state['id']);self.assertEqual(approved['approved_brief']['text'],draft)
        edited=draft+'\nUse accessible labels on icons.'
        next(w for w in app.text_area if w.label=='Editable design brief').set_value(edited)
        next(b for b in app.button if b.label=='Build, check and host locally').click().run()
        self.assertFalse(app.exception)
        saved=d.load(state['id']);self.assertIsNone(saved['approved_brief'])
        self.assertEqual(saved['draft_brief'],edited)

    def test_ui_cannot_approve_without_the_review_checkbox(self):
        state=d.save(d.confirm_summary(complete(self.reply())),expected_revision=self.state['revision'])
        app=AppTest.from_string(f"import streamlit as st\nfrom interview_ui import render_interview\nst.session_state['design_interview_id']={state['id']!r}\nrender_interview(lambda job:None)",default_timeout=15).run()
        next(b for b in app.button if b.label=='Approve design brief').click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(d.load(state['id'])['approved_brief'])
        self.assertTrue(any('approval checkbox' in error.value for error in app.error))
