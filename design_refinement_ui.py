"""Review real AI art direction before approving the generation brief."""
import streamlit as st
import design_interview as interview
import design_refinement as refinement
from text_safety import markdown_text


def request_refinement(state, perform_job):
    outcome = perform_job({'workflow': 'interview_refine', 'interview_id': state['id'], 'revision': state['revision']})
    latest = interview.load(state['id'])
    # API-key admission and interrupted workers may return before the worker can
    # save a failure. Persist that outcome once; rerenders must not spend credits.
    if refinement.current(latest) is None or (latest['revision'] == state['revision'] and not (isinstance(outcome, dict) and outcome.get('ok'))):
        message = outcome.get('error', 'No design proposal was returned. Retry or use your original brief.') if isinstance(outcome, dict) else 'No design proposal was returned. Retry or use your original brief.'
        interview.save(refinement.failed(latest, ValueError(message)), expected_revision=latest['revision'])
    st.rerun()


def render_design_refinement(state, perform_job):
    record = refinement.current(state)
    attempt_key = 'design_refinement_attempt_' + state['id'] + '_' + refinement.fingerprint(state)
    auto = state.get('auto_design_refinement', False) and not state.get('summary_approval') and not state.get('approved_brief')
    if record is None and auto and not st.session_state.get(attempt_key):
        st.session_state[attempt_key] = True
        st.write('Refining the layout, visual identity and purposeful motion before you review the brief…')
        request_refinement(state, perform_job)
        return

    with st.container(border=True):
        st.subheader('AI design refinement')
        if record and record['status'] == 'ready':
            st.write(markdown_text(record['plan']['concept']))
            st.caption('A proposed execution plan, not a design-quality score. Review or edit it in the brief below. Your features, selected style, theme and palette remain the constraints.')
            with st.expander('Layout, visual details and animations'):
                for key, (label, _) in refinement.TEXT_FIELDS.items():
                    if key != 'concept':
                        st.markdown('**' + label + '**')
                        st.write(markdown_text(record['plan'][key]))
                st.markdown('**Motion**')
                for motion in record['plan']['motion']:
                    st.write(markdown_text(f"{motion['trigger']} → {motion['effect']} · {motion['duration_ms']} ms"))
                st.caption('Reduced motion keeps content visible and controls usable.' if record['plan']['motion'] else 'Animated entrances and interactions are disabled in this proposal.')
        elif record and record['status'] == 'failed':
            st.warning(markdown_text(record.get('error') or 'Design refinement could not finish.'))
            st.caption('Your original requirements are kept. Retry the design pass or approve the original brief below.')
        elif record and record['status'] == 'skipped':
            st.caption('Using your original brief. The extra AI design pass is skipped.')
        else:
            st.write('Ask Nemotron for a subject-specific layout, stronger hierarchy, visual details and suitable animations before coding.')
            st.caption('This extra design pass uses Nebius credits, with at most one schema-correction retry. It does not add pages or features.')
        actions = st.columns(2)
        if actions[0].button('Refine design again' if record and record['status'] == 'ready' else 'Refine the design with AI', key='refine_design_action'):
            request_refinement(state, perform_job)
        if record and record['status'] == 'ready' and actions[1].button('Use original brief', key='skip_design_refinement'):
            interview.save(refinement.skip(state), expected_revision=state['revision'])
            st.rerun()
