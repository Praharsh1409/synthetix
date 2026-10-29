"""A guided design interview: one decision, three AI suggestions, one custom answer."""
from copy import deepcopy

import streamlit as st
import design_interview as interview
import guided_interview as guided
from design_styles import STYLES, compatibility, preview
from text_safety import markdown_text
from runtime_paths import cloud_mode
from design_refinement_ui import render_design_refinement


def text(value):
    return markdown_text(str(value))


def select_interview(identifier):
    if st.query_params.get('interview') != identifier:
        st.query_params['interview'] = identifier
    st.session_state['design_interview_id'] = identifier


def commit(state, updated):
    saved = interview.save(updated, expected_revision=state['revision'])
    st.rerun()
    return saved


def request_reply(state, perform_job):
    perform_job({'workflow': 'interview_turn', 'interview_id': state['id'], 'revision': state['revision']})
    st.rerun()


def request_suggestions(state, perform_job):
    if state['pending']:
        request_reply(state, perform_job)
    else:
        updated = interview.queue_message(state, 'Continue to the next undecided requirement. Give three project-specific suggestions; keep my saved answers.')
        saved = interview.save(updated, expected_revision=state['revision'])
        request_reply(saved, perform_job)


def render_start(perform_job):
    st.header('What are we making?')
    st.write('Describe the idea. We will work through one decision at a time, refine the design and motion, then build from your approved brief.')
    with st.form('new_design_interview'):
        kind = st.selectbox('Project starting point', ['Custom website', 'Portfolio', 'SaaS landing page', 'Dashboard', 'E-commerce frontend', 'Blog', 'Educational website', 'Developer tool'])
        initial = st.text_area('Describe your website idea', max_chars=3800, height=140,
            placeholder='For example: a photography portfolio for local clients, with a filterable gallery and a warm editorial feel.')
        st.caption('Self-contained HTML/CSS/JavaScript. AI requests use Nebius credits. Answers are saved in this temporary session.' if cloud_mode() else 'Self-contained HTML/CSS/JavaScript. AI requests use Nebius credits. Your answers are saved locally.')
        begin = st.form_submit_button('Begin design interview', type='primary')
    if begin:
        try:
            if not initial.strip():
                raise ValueError('Describe what you want to create, even if it is only a rough idea.')
            state = interview.create((kind + ': ' if kind != 'Custom website' else '') + initial)
            select_interview(state['id'])
            request_reply(state, perform_job)
        except (ValueError, OSError) as error:
            st.error(text(error))


def render_question(state, perform_job):
    question = guided.question(state)
    if not question:
        return
    field = question['field']
    title = question['text'] if question['text'].count('?') <= 1 else guided.QUESTIONS[field]
    st.subheader(title)
    st.caption('Choose an AI suggestion, or select Custom answer and write your own. Your choice is saved before moving on.')
    if state.get('last_error'):
        st.error(text(state['last_error']))
    options = question['options']
    labels = [text(option['label']) for option in options] + ['Custom answer']
    if not options:
        st.info('AI suggestions are unavailable for this decision. Retry them or continue with your own answer.')
        if st.button('Get three AI suggestions', key='question_suggestions_' + field):
            request_suggestions(state, perform_job)
    key = state['id'] + '_' + field + '_' + interview.digest(options)[:10]
    selected = st.radio('Choose your answer', labels, index=None, key='guided_answer_' + key)
    answer = ''
    if selected == 'Custom answer':
        answer = st.text_area('Your custom answer', max_chars=1200, height=110, key='guided_custom_' + key)
    elif selected is not None:
        option = options[labels.index(selected)]
        st.write(text(option['value']))
        st.caption('Why this fits: ' + text(option['reason']))
        answer = option['value']
    if st.button('Save answer and continue', type='primary', disabled=selected is None, key='guided_continue_' + key):
        try:
            updated = guided.answer(state, field, answer)
            saved = interview.save(updated, expected_revision=state['revision'])
            if saved['pending']:
                request_reply(saved, perform_job)
            else:
                st.rerun()
        except (ValueError, OSError) as error:
            st.error(text(error))


def render_catalog():
    with st.expander('Explore all 15 design styles'):
        st.caption('These are authored CSS illustrations of each style. They are not generated website previews.')
        for offset in range(0, len(STYLES), 2):
            columns = st.columns(2, gap='medium')
            for column, name in zip(columns, list(STYLES)[offset:offset + 2]):
                with column, st.container(key='style-card-' + str(list(STYLES).index(name))):
                    item = STYLES[name]
                    st.html(preview(name))
                    st.markdown('**' + name + '**')
                    st.write(item['explanation'])
                    st.caption('Useful for: ' + item['use_cases'])
                    st.caption('Trade-off: ' + item['downside'])


def render_styles(state, perform_job):
    st.subheader('Choose your website’s design')
    st.write('Your main requirements are captured. Pick a visual direction to continue to the remaining details.')
    options = guided.style_options(state)
    if state.get('last_error'):
        st.warning(text(state['last_error']))
    if not options:
        st.info('Ask the AI for three design directions, or choose your own from the full style catalog.')
        if st.button('Get three AI design recommendations'):
            request_suggestions(state, perform_job)
    labels = [text(option['label']) for option in options] + ['Custom design']
    selected = st.radio('Choose a design direction', labels, index=None,
        key='guided_style_choice_' + state['id'] + '_' + interview.digest(options)[:10])
    chosen = []
    if selected == 'Custom design':
        chosen = st.multiselect('Choose your styles (up to three)', list(STYLES), default=interview.styles(state),
            max_selections=3, help='The first style is primary. Use the others for supporting details.',
            key='guided_custom_styles_' + state['id'] + '_' + str(state['revision']))
    elif selected is not None:
        option = options[labels.index(selected)]
        chosen = option['value'].split(' + ')
        st.write('**Why it fits:** ' + text(option['reason']))
        st.caption('Trade-off: ' + text(option['tradeoff']))
        for name in chosen:
            st.html(preview(name))
    acknowledged = False
    warnings = compatibility(chosen)
    if warnings:
        for warning in warnings:
            st.warning(text(warning))
        acknowledged = st.checkbox('I understand the trade-offs and want this combination', key='guided_style_ack_' + interview.digest(chosen))
    if st.button('Use this design and continue', type='primary', disabled=not chosen or bool(warnings and not acknowledged)):
        try:
            updated = guided.select_styles(state, chosen, acknowledge=acknowledged)
            saved = interview.save(updated, expected_revision=state['revision'])
            if saved['pending']:
                request_reply(saved, perform_job)
            else:
                st.rerun()
        except (ValueError, OSError) as error:
            st.error(text(error))
    render_catalog()


def launch_build(state, counter, start_build):
    request = guided.build_request(state, counter)
    if start_build is not None:
        start_build(request)
    else:
        # A real navigation callback is supplied by app.py. Keeping the request allows
        # embedded views/tests to inspect the transition without performing model work.
        st.session_state['website_review_request'] = request
        st.success('Your approved website is queued on Review the website.')


def render_final(state, perform_job, start_build=None):
    st.subheader('Review your website brief')
    st.write('This is what the builder will use. Approving starts real website generation and opens Review the website.')
    missing = [value for value in interview.blockers(state) if not value.startswith('Review style-dependent decisions:')]
    if missing:
        st.info('Before building: ' + text('; '.join(missing)))
        if state['pending']:
            if state.get('last_error'):
                st.error(text(state['last_error']))
            if st.button('Retry the unfinished AI reply'):
                request_reply(state, perform_job)
            if st.button('Review the saved answers without another AI reply'):
                updated = deepcopy(state)
                updated.update(pending=False, last_error=None)
                commit(state, updated)
        return
    render_design_refinement(state, perform_job)
    draft_value = state['draft_brief'] or interview.render_brief(state)
    approved = state.get('approved_brief')
    with st.form('final_design_brief_' + str(state['revision'])):
        draft = st.text_area('Editable design brief', value=draft_value, height=360, max_chars=12000)
        validation = st.selectbox('Validation', ['Runtime errors only', 'Counter behaviour + runtime'], key='interview_build_checks')
        st.caption('Counter checks are only suitable for Increase, Decrease and Reset interfaces. Runtime checks alone do not establish every requested behaviour.')
        reviewed = st.checkbox('I approve this exact design brief', key='approve_brief_' + interview.digest(draft_value))
        approve = st.form_submit_button('Approve brief and build website', type='primary')
    if approve:
        if not reviewed:
            st.error('Review the brief and select the approval checkbox before building.')
        else:
            try:
                saved = interview.save(guided.approve(state, draft), expected_revision=state['revision'])
                launch_build(saved, validation == 'Counter behaviour + runtime', start_build)
            except (ValueError, OSError) as error:
                st.error(text(error))
    if approved:
        st.caption('A previously approved brief is saved. The checkbox above approves the currently displayed text before a new build.')
    st.download_button('Download planning brief', draft_value, file_name='synthetix-design-brief.txt', mime='text/plain')


def render_previous_answers(state):
    with st.expander('Edit earlier answers'):
        st.caption('Changing a saved decision requires fresh brief approval. Other answers are kept.')
        with st.form('guided_decision_editor_' + str(state['revision'])):
            changes = {}
            for key in [*guided.CORE, *guided.VISUAL]:
                changes[key] = st.text_area(interview.FIELDS[key], value=state['requirements'][key]['value'], height=75, max_chars=1200)
            saved = st.form_submit_button('Save changed answers')
        if saved:
            try:
                updated = deepcopy(state)
                updated.update(pending=False, last_error=None)
                updated = interview.update_requirements(updated, changes)
                commit(state, updated)
            except (ValueError, OSError) as error:
                st.error(text(error))


def render_live_brief(state):
    with st.container(key='interview-live-brief'):
        st.subheader('Your website so far')
        st.caption('Saved locally · revision ' + str(state['revision']))
        for key in ('purpose', 'audience', 'goals', 'selected_styles', 'functionality'):
            item = state['requirements'][key]
            st.markdown('**' + interview.FIELDS[key] + '**')
            st.write(text(item['value'] or 'Not decided yet'))
            if item['value']:
                st.caption('Your choice' if item['status'] == 'confirmed' else 'Extracted from your description; review in the brief')


def render_interview(perform_job, start_build=None):
    saved = interview.list_interviews()
    with st.expander('Resume a saved design interview'):
        if saved:
            selected = st.selectbox('Saved interview', saved, format_func=lambda value: value['title'] + ' · ' + value['id'][:6])
            if st.button('Resume interview'):
                select_interview(selected['id']); st.rerun()
        else:
            st.caption('Your saved conversations will appear here.')
    identifier = st.query_params.get('interview') or st.session_state.get('design_interview_id')
    if not identifier:
        render_start(perform_job)
        return
    try:
        state = interview.load(identifier)
    except (ValueError, OSError) as error:
        st.error(text(error))
        if st.button('Start a new interview'):
            st.query_params.pop('interview', None); st.session_state.pop('design_interview_id', None); st.rerun()
        return
    select_interview(identifier)
    current = guided.step(state)
    with st.container(key='interview-heading'):
        heading, action = st.columns([3, 1])
        with heading:
            st.header({'idea': 'Understand the idea', 'design': 'Choose the design', 'details': 'Refine the details', 'brief': 'Approve and build'}[current])
            st.caption('Idea → Design → Details → Visual refinement → Approval → Review the website')
        if action.button('New interview', width='stretch'):
            st.query_params.pop('interview', None); st.session_state.pop('design_interview_id', None); st.rerun()
    # One primary decision in the 2.2:1 canvas/summary grid. Phones stack the rail.
    left, right = st.columns([2.2, 1], gap='large')
    with left, st.container(key='interview-canvas'):
        if current in ('idea', 'details'):
            render_question(state, perform_job)
        elif current == 'design':
            render_styles(state, perform_job)
        else:
            render_final(state, perform_job, start_build)
        with st.expander('Conversation history'):
            for message in state['conversation']:
                st.write(('You: ' if message['role'] == 'user' else 'Synthetix: ') + text(message['content']))
        render_previous_answers(state)
        if current in ('details', 'brief') and st.button('Change the design direction'):
            updated = deepcopy(state); interview.invalidate(updated)
            updated.update(design_confirmed=False, pending=False, last_error=None)
            commit(state, updated)
    with right:
        render_live_brief(state)
