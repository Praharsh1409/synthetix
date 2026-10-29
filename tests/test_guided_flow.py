from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import design_interview as d
import guided_interview as g
import generation_ui as progress
import synthetix


def choices():
    return [
        {'label':'Students','value':'Students practising coding','reason':'Matches the learning goal.'},
        {'label':'Developers','value':'Working software developers','reason':'Prioritises useful technical detail.'},
        {'label':'Recruiters','value':'Recruiters reviewing project work','reason':'Prioritises evidence and clear summaries.'},
    ]


def reply(field='audience', updates=None):
    return {'message':'Who is it for? What should it do? Which style?', 'updates':updates or {},
            'questions':[{'field':field,'text':g.QUESTIONS.get(field,'Which option fits?'),'conflict':False,'options':choices()}],
            'recommendations':[]}


def ready(state):
    state.update(pending=False,last_error=None)
    return d.update_requirements(state,{'purpose':'A study counter','audience':'Students','goals':'Track repetitions',
        'pages':'One page with a heading, count, Increase, Decrease and Reset',
        'functionality':'Increase adds exactly 1, Decrease subtracts 1, Reset sets 0.',
        'selected_styles':'Minimalism + Bento UI','theme':'Light','palette':'White, charcoal and blue','layout':'Compact centred panel'})


class GuidedFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.object(d,'STORE',Path(self.temp.name)/'interviews');self.patch.start()
        self.state=d.create('A website for practising coding')

    def tearDown(self):
        self.patch.stop();self.temp.cleanup()

    def test_selected_answer_is_bound_and_saved_before_next_model_call(self):
        state=d.update_requirements(self.state,{'purpose':'A coding practice site'})
        state['pending']=False
        saved=d.save(g.answer(state,'audience','Students'),expected_revision=self.state['revision'])
        self.assertEqual(d.load(saved['id'])['requirements']['audience']['value'],'Students')
        with self.assertRaises(TimeoutError):d.respond(saved,ask=lambda *_:(_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(d.load(saved['id'])['requirements']['audience']['status'],'confirmed')
        self.assertEqual(g.next_field(saved),'goals')

    def test_already_answered_field_cannot_be_submitted_again(self):
        state=ready(self.state)
        with self.assertRaisesRegex(ValueError,'already been answered'):g.answer(state,'audience','Someone else')

    def test_model_cannot_overwrite_explicit_answer_or_echo_discarded_questions(self):
        state=d.update_requirements(self.state,{'purpose':'A coding tool','audience':'Students'})
        state['pending']=True
        calls=[]
        def ask(system,context):
            calls.append(json.loads(context))
            return reply('audience',{'audience':'Enterprise buyers'}) if len(calls)==1 else reply('goals')
        result=d.respond(state,ask=ask)
        self.assertEqual(result['requirements']['audience']['value'],'Students')
        self.assertEqual(len(result['questions']),1)
        self.assertEqual(result['questions'][0]['field'],'goals')
        self.assertNotIn('Who is it for?',result['conversation'][-1]['content'])
        self.assertEqual(len(calls),2)

    def test_invalid_suggestions_have_bounded_retry_and_custom_recovery(self):
        state=d.update_requirements(self.state,{'purpose':'A coding tool'})
        calls=[]
        def ask(*args):calls.append(1);return {'message':'Again?','updates':{},'questions':[],'recommendations':[]}
        result=d.respond(state,ask=ask)
        self.assertEqual(len(calls),2)
        self.assertFalse(result['pending'])
        self.assertEqual(g.question(result)['options'],[])
        custom=g.answer(result,'audience','My classmates')
        self.assertEqual(custom['requirements']['audience']['value'],'My classmates')

    def test_extra_requirements_are_extracted_before_selecting_next_question(self):
        state=d.update_requirements(self.state,{'purpose':'A study counter','audience':'Students','goals':'Track repetitions; one page; Increase adds 1; light theme.'})
        calls=[]
        recommendation={'field':'selected_styles','value':'Minimalism','reason':'Keeps the counter easy to read.',
            'tradeoff':'Needs good type hierarchy.','alternatives':[
                {'value':'Bento UI','tradeoff':'Groups the controls into a clear panel.'},
                {'value':'Material Design','tradeoff':'Uses more conventional control states.'}]}
        def ask(system,context):
            data=json.loads(context);calls.append((system,data))
            if len(calls)==1:
                return {'message':'Captured','updates':{'pages':'One counter page','functionality':'Increase adds 1','theme':'Light'},'questions':[],'recommendations':[]}
            self.assertEqual(data['requirements']['pages']['value'],'One counter page')
            return {'message':'Choose a design','updates':{},'questions':[],'recommendations':[recommendation]}
        result=d.respond(state,ask=ask)
        self.assertIn('extraction ONLY',calls[0][0])
        self.assertEqual(result['questions'],[])
        self.assertEqual(g.step(result),'design')
        self.assertEqual(len(g.style_options(result)),3)

    def test_three_suggestions_must_be_distinct_and_complete(self):
        self.assertEqual(len(g.valid_options(choices())),3)
        for bad in [choices()[:2],choices()+choices()[:1],[choices()[0]]*3]:
            with self.assertRaises(ValueError):g.valid_options(bad)

    def test_core_completion_automatically_changes_to_design_step(self):
        state=ready(self.state)
        self.assertEqual(g.step(state),'design')
        state=g.select_styles(state,['Minimalism','Bento UI'])
        self.assertEqual(g.step(state),'brief')
        self.assertEqual(state['requirements']['audience']['value'],'Students')

    def test_design_selection_advances_only_to_unanswered_details(self):
        state=ready(self.state)
        state=d.update_requirements(state,{'palette':''})
        state=g.select_styles(state,['Editorial Design','Minimalism'])
        self.assertEqual(g.step(state),'details')
        self.assertEqual(g.next_field(state),'palette')
        self.assertEqual(state['requirements']['theme']['value'],'Light')

    def test_last_detail_advances_to_brief_without_final_model_round_trip(self):
        state=ready(self.state)
        state=d.update_requirements(state,{'layout':''});state['design_confirmed']=True
        state=g.answer(state,'layout','Spacious centred reading column')
        self.assertFalse(state['pending']);self.assertEqual(g.step(state),'brief')

    def test_conflicting_styles_require_acknowledgement(self):
        state=ready(self.state)
        with self.assertRaises(ValueError):g.select_styles(state,['Minimalism','Maximalism'])
        selected=g.select_styles(state,['Minimalism','Maximalism'],acknowledge=True)
        self.assertEqual(selected['conflict_ack'],d.digest(['Minimalism','Maximalism']))

    def test_history_without_new_guidance_fields_can_still_resume(self):
        loaded=d.load(self.state['id'])
        self.assertNotIn('design_confirmed',loaded)
        self.assertEqual(g.step(loaded),'idea')

    def test_approval_prepares_exact_brief_and_generation_request(self):
        state=g.select_styles(ready(self.state),['Minimalism'])
        draft=d.render_brief(state)+'\nUse visible keyboard focus.'
        approved=g.approve(state,draft)
        saved=d.save(approved,expected_revision=self.state['revision'])
        job=g.build_request(saved,counter=True)
        self.assertEqual(saved['approved_brief']['text'],draft)
        self.assertEqual(job['revision'],saved['revision'])
        self.assertTrue(job['use_counter_checks'])
        changed=d.update_requirements(saved,{'audience':'Different audience'})
        with self.assertRaises(ValueError):g.build_request(changed)

    def test_ui_has_three_ai_answers_and_custom_as_primary_input(self):
        state=d.update_requirements(self.state,{'purpose':'A coding practice page'})
        state.update(pending=False,questions=reply()['questions'])
        saved=d.save(state,expected_revision=self.state['revision'])
        code=f"""
import streamlit as st
from interview_ui import render_interview
st.session_state['design_interview_id']={saved['id']!r}
render_interview(lambda job:None)
"""
        app=AppTest.from_string(code,default_timeout=15).run()
        self.assertFalse(app.exception)
        radio=next(r for r in app.radio if r.label=='Choose your answer')
        self.assertEqual(radio.options,['Students','Developers','Recruiters','Custom answer'])
        self.assertFalse(any(t.label=='Message your design partner' for t in app.text_area))
        radio.set_value('Custom answer').run()
        next(t for t in app.text_area if t.label=='Your custom answer').set_value('First-year engineering students')
        next(b for b in app.button if b.label=='Save answer and continue').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(d.load(saved['id'])['requirements']['audience']['value'],'First-year engineering students')

    def test_ui_approval_dispatches_review_request_without_separate_build_click(self):
        state=g.select_styles(ready(self.state),['Minimalism'])
        saved=d.save(state,expected_revision=self.state['revision'])
        code=f"""
import streamlit as st
from interview_ui import render_interview
st.session_state['design_interview_id']={saved['id']!r}
def navigate(job):
    st.session_state['destination']='review'
    st.session_state['dispatched']=job
render_interview(lambda job:None,navigate)
"""
        app=AppTest.from_string(code,default_timeout=15).run()
        next(c for c in app.checkbox if c.label=='I approve this exact design brief').check()
        next(b for b in app.button if b.label=='Approve brief and build website').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['destination'],'review')
        self.assertEqual(app.session_state['dispatched']['approval_hash'],d.load(saved['id'])['approved_brief']['hash'])


class GenerationProgressTests(unittest.TestCase):
    def test_progress_changes_only_on_real_milestones_and_failure_never_reaches_100(self):
        value=0
        for line in ['Generating...', 'PASS: a check', '120 seconds elapsed', progress.PREFIX+'garbage']:
            value=progress.completed_from_line(line,value)
        self.assertEqual(value,0)
        self.assertEqual(progress.completed_from_line(progress.PREFIX+'{"stage":"saved"}',0),0)
        for stage,_ in progress.STAGES:
            value=progress.completed_from_line(progress.PREFIX+json.dumps({'stage':stage}),value)
        self.assertEqual(value,4)
        self.assertEqual(progress.completed_from_line(progress.PREFIX+'{"stage":"brief"}',value),4)

    def test_success_requires_saved_html_and_passed_browser_report(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(progress,'ROOT',Path(temp)):
            folder=Path(temp)/'artifacts'/'synthetix_fixture';folder.mkdir(parents=True)
            outcome={'ok':True,'output_folder':str(folder)}
            (folder/'summary.json').write_text(json.dumps({'status':'no_runtime_errors_observed','current_version':0}))
            self.assertFalse(progress.successful_result(outcome))
            (folder/'final.html').write_text('<html>Actual source</html>')
            (folder/'report_0.json').write_text(json.dumps({'passed':False,'combined_errors':{'javascript_errors':['broken']}}))
            self.assertFalse(progress.successful_result(outcome))
            (folder/'report_0.json').write_text(json.dumps({'passed':True,'combined_errors':{'javascript_errors':[],'console_errors':[],'behavior_errors':[],'execution_errors':[]}}))
            self.assertTrue(progress.successful_result(outcome))

    def test_malformed_worker_result_is_a_stopped_build_not_a_crash(self):
        app=AppTest.from_string("""
from generation_ui import render_generation
import streamlit as st
def malformed(*args,**kwargs):return None
st.session_state['result']=render_generation({},malformed)
""",default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state['result']['ok'])
        self.assertTrue(app.error)

    def test_successful_generation_replaces_loading_panel_with_compact_completion(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(progress,'ROOT',Path(temp)):
            root=Path(temp);(root/'assets').mkdir()
            actual=Path(progress.__file__).parent/'assets'/'synthetix-loading-logo.png'
            (root/'assets'/'synthetix-loading-logo.png').write_bytes(actual.read_bytes())
            folder=root/'artifacts'/'synthetix_complete';folder.mkdir(parents=True)
            (folder/'final.html').write_text('<html>Ready for review</html>')
            (folder/'summary.json').write_text(json.dumps({'status':'no_runtime_errors_observed'}))
            (folder/'report_0.json').write_text(json.dumps({'passed':True,'combined_errors':{'javascript_errors':[],'console_errors':[],'behavior_errors':[],'execution_errors':[]}}))
            script=f"""
import streamlit as st
from generation_ui import render_generation
def complete(*args,**kwargs):return {{'ok':True,'output_folder':{str(folder)!r}}}
st.session_state['result']=render_generation({{}},complete)
"""
            app=AppTest.from_string(script,default_timeout=15).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state['result']['ok'])
            self.assertFalse(any('being prepared' in heading.value for heading in app.subheader))

    def test_failed_generation_never_emits_checked_or_saved_milestones(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(synthetix,'PROJECT_FOLDER',Path(temp)),patch.object(synthetix,'generate_html',side_effect=TimeoutError('model unavailable')):
            events=[]
            result=synthetix.run_pipeline('A counter',progress=events.append)
            self.assertEqual(result['status'],'generation_failed')
            self.assertEqual(events,[])

    def test_review_resume_requires_the_same_approved_brief(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(progress,'ROOT',Path(temp)):
            folder=Path(temp)/'artifacts'/'synthetix_saved';folder.mkdir(parents=True)
            (folder/'final.html').write_text('<html>Saved website</html>')
            (folder/'summary.json').write_text(json.dumps({'status':'no_runtime_errors_observed'}))
            (folder/'report_0.json').write_text(json.dumps({'passed':True,'combined_errors':{'javascript_errors':[],'console_errors':[],'behavior_errors':[],'execution_errors':[]}}))
            state={'approved_brief':{'hash':'approved'},'build_runs':[{'approval_hash':'approved','folder':str(folder)}]}
            self.assertTrue(progress.saved_review(state)['ok'])
            state['approved_brief']['hash']='different brief'
            self.assertIsNone(progress.saved_review(state))

    def test_review_resume_does_not_turn_missing_code_into_success(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(progress,'ROOT',Path(temp)):
            folder=Path(temp)/'artifacts'/'synthetix_missing';folder.mkdir(parents=True)
            (folder/'summary.json').write_text(json.dumps({'status':'no_runtime_errors_observed'}))
            state={'approved_brief':{'hash':'approved'},'build_runs':[{'approval_hash':'approved','folder':str(folder)}]}
            self.assertFalse(progress.saved_review(state)['ok'])
