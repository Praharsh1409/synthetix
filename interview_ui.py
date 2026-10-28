"""Streamlit design partnership, built on the existing worker and design tokens."""
from copy import deepcopy
import html

import streamlit as st
import design_interview as interview
from design_styles import STYLES, compatibility, preview, recommend, recommended_combination
from text_safety import markdown_text


def text(value):return markdown_text(str(value))


def commit(state, updated):
    try:
        interview.save(updated,expected_revision=state['revision'])
        st.rerun()
    except (OSError,ValueError) as error:
        st.error(text(error))


def select_interview(identifier):
    if st.query_params.get('interview')!=identifier:st.query_params['interview']=identifier
    st.session_state['design_interview_id']=identifier


def request_reply(state, perform_job):
    perform_job({'workflow':'interview_turn','interview_id':state['id'],'revision':state['revision']})
    st.rerun()


def render_start(perform_job):
    st.header('What are we making?')
    st.write('Tell your design partner the idea. Together, choose what it should do and how it should feel before writing code.')
    with st.form('new_design_interview'):
        kind=st.selectbox('Project starting point',['Custom website','Portfolio','SaaS landing page','Dashboard','E-commerce frontend','Blog','Educational website','Developer tool'])
        initial=st.text_area('Describe your website idea',max_chars=3800,height=140,
             placeholder='For example: a portfolio for my photography, aimed at local clients. I want a warm editorial feel and a filterable gallery.')
        st.caption('The prototype builds one self-contained HTML/CSS/JavaScript file. AI replies use Nebius credits. Your planning conversation is saved on this computer.')
        begin=st.form_submit_button('Begin design interview',type='primary')
    if begin:
        try:
            if not initial.strip():raise ValueError('Describe what you want to create, even if you only have a rough idea.')
            state=interview.create((kind+': ' if kind!='Custom website' else '')+initial)
            select_interview(state['id'])
            request_reply(state,perform_job)
        except (ValueError,OSError) as error:st.error(text(error))


def render_conversation(state, perform_job):
    st.subheader('Work through the idea')
    st.caption('AI suggestions are proposals. Your saved decisions and final approval take precedence.')
    # Use the page's keyboard-accessible scrolling rather than an unfocusable nested well.
    if len(state['conversation'])>6:
        with st.expander('Earlier questions and answers'):
            for message in state['conversation'][:-6]:
                st.write(('You: ' if message['role']=='user' else 'Design partner: ')+text(message['content']))
    with st.container(key='design-conversation'):
        for message in state['conversation'][-6:]:
            with st.chat_message(message['role'],avatar=':material/person:' if message['role']=='user' else ':material/edit_note:'):
                st.write(text(message['content']))
    if state['pending']:
        if state['last_error']:st.error(text(state['last_error']))
        st.info('Your message is saved. The AI reply is unfinished; retry it or continue using the decision editor.')
        a,b=st.columns(2)
        if a.button('Retry AI reply',key='retry_design_reply'):request_reply(state,perform_job)
        if b.button('Continue without this reply',key='dismiss_design_reply'):
            updated=deepcopy(state);updated.update(pending=False,last_error=None)
            commit(state,updated)
    else:
        with st.form('design_message_form',clear_on_submit=True):
            answer=st.text_area('Message your design partner',max_chars=4000,height=100,
                placeholder='Answer a question, ask why, reject a recommendation, or describe a change.')
            sent=st.form_submit_button('Send message',type='primary')
        if sent:
            try:
                queued=interview.save(interview.queue_message(state,answer),expected_revision=state['revision'])
                request_reply(queued,perform_job)
            except (ValueError,OSError) as error:st.error(text(error))
    if state['questions']:
        st.markdown('**Questions to resolve**')
        for q in state['questions']:st.write(('Clarify: ' if q['conflict'] else '• ')+text(q['text']))
    render_recommendations(state)


def render_recommendations(state):
    if not state['recommendations']:
        st.caption('Contextual AI recommendations will appear after a successful reply. The style explorer also has a local, explainable ranking.')
        return
    st.subheader('AI recommendations')
    for index,rec in enumerate(state['recommendations']):
        with st.expander(interview.FIELDS[rec['field']]+' — '+text(rec['value'][:70])):
            st.write('**Proposed:** '+text(rec['value']))
            st.write('**Why:** '+text(rec['reason']))
            st.write('**Trade-off:** '+text(rec['tradeoff']))
            current=state['requirements'][rec['field']]
            st.caption('Current decision: '+text(current['value'] or 'Not decided')+' · '+current['status'])
            if st.button('Accept recommendation',key=f'accept_design_rec_{index}'):
                commit(state,interview.update_requirements(state,{rec['field']:rec['value']},source='AI recommendation accepted by you'))
            for j,alt in enumerate(rec['alternatives']):
                st.write('**Alternative:** '+text(alt['value'])+' — '+text(alt['tradeoff']))
                if st.button('Choose this alternative',key=f'accept_design_alt_{index}_{j}'):
                    commit(state,interview.update_requirements(state,{rec['field']:alt['value']},source='AI alternative accepted by you'))
            st.caption('To reject or customise, describe the change in chat or edit this decision in Review decisions.')


def render_styles(state):
    ranked=recommend(state['requirements'],state['initial_request'])
    selected=interview.styles(state)
    st.subheader('Find a visual direction')
    st.caption('These previews are distinct, authored CSS illustrations of each style—not product screenshots or model-generated designs.')
    st.markdown('**Recommended starting points**')
    st.caption('Local recommendation rubric: explicit preferences, purpose, audience, content density, interaction needs and accessibility. These rankings are not AI confidence scores.')
    for i,item in enumerate(ranked,1):
        st.write(f'**{i}. {item["name"]}** — '+text(item['reason']))
        st.caption('Trade-off: '+text(item['tradeoff']))
    combination=recommended_combination(ranked)
    if st.button('Use recommended combination: '+' + '.join(combination),key='use_ranked_design'):
        commit(state,interview.update_requirements(state,{'selected_styles':' + '.join(combination)},source='Local recommendation accepted by you'))
    with st.form('select_design_styles'):
        choices=st.multiselect('Choose your styles (up to three)',list(STYLES),default=selected,max_selections=3,
                              help='Order matters: the first style controls the overall composition; the others have supporting roles.',key='design_styles_'+state['id']+'_'+str(state['revision']))
        st.caption('Compatible examples: Bento UI + Minimalism; Glassmorphism + Minimalism; Editorial Design + Minimalism; Cyberpunk + Bento UI; Material Design + Flat Design.')
        chosen=st.form_submit_button('Save style selection')
    if chosen:commit(state,interview.update_requirements(state,{'selected_styles':' + '.join(choices)}))
    st.write('**Selected:** '+text(' + '.join(selected) or 'No style selected yet'))
    st.write('**Recommended:** '+text(' + '.join(combination)))
    warnings=compatibility(selected)
    if warnings:
        for warning in warnings:st.warning(text(warning))
        st.caption('You can keep an unusual combination after acknowledging the trade-offs. Define the primary style and the role of each accent in Layout.')
        if state['conflict_ack']!=interview.digest(selected):
            if st.button('Keep this combination; I understand the trade-offs'):
                updated=deepcopy(state);updated['conflict_ack']=interview.digest(selected);interview.invalidate(updated);commit(state,updated)
        else:st.caption('Combination trade-offs acknowledged by you.')
    # Catalog arithmetic: two equal columns + one 16px gutter; phone stacks to one.
    for offset in range(0,len(STYLES),2):
        columns=st.columns(2,gap='medium')
        for column,name in zip(columns,list(STYLES)[offset:offset+2]):
            with column,st.container(key='style-card-'+str(list(STYLES).index(name))):
                st.html(preview(name))
                st.markdown('**'+name+(' · Selected' if name in selected else '')+'**')
                item=STYLES[name]
                st.write(item['explanation'])
                with st.expander('Characteristics and trade-offs: '+name):
                    st.write('**Visual traits:** '+item['characteristics'])
                    st.write('**Useful for:** '+item['use_cases'])
                    st.write('**Watch for:** '+item['downside'])
                    st.write('**Combines with:** '+', '.join(item['compatible']))
                if st.button(('Remove '+name) if name in selected else ('Select '+name),key='toggle_style_'+name,disabled=name not in selected and len(selected)>=3):
                    updated_styles=[v for v in selected if v!=name] if name in selected else selected+[name]
                    commit(state,interview.update_requirements(state,{'selected_styles':' + '.join(updated_styles)}))


def render_decisions(state):
    st.subheader('Here is what I understand you want to build')
    st.caption('Edit any decision below. Saving confirms the values you reviewed; the final summary approval remains a separate step. Empty optional decisions are listed as assumptions.')
    if state['style_recheck']:
        st.warning('The visual direction changed. Review '+', '.join(interview.FIELDS[k] for k in state['style_recheck'])+'. Your other requirements were kept.')
    with st.form('design_decision_editor_'+str(state['revision'])):
        values={'technical':state['requirements']['technical']['value']}
        for title,keys in [
          ('Purpose and functionality',['purpose','audience','goals','pages','functionality']),
          ('Visual decisions',['theme','palette','typography','layout','interactions','branding']),
          ('Constraints and exclusions',['responsive','accessibility','exclusions'])]:
            with st.expander(title,expanded=title=='Purpose and functionality'):
                for key in keys:
                    item=state['requirements'][key]
                    values[key]=st.text_area(interview.FIELDS[key],value=item['value'],max_chars=1200,height=75,key='decision_'+key+'_'+str(state['revision']))
                    st.caption(item['status'].capitalize()+' · '+item['source'])
        st.caption('Styles are edited in Style explorer. Fixed platform scope: '+interview.SCOPE)
        saved=st.form_submit_button('Save reviewed decisions',type='primary')
    if saved:
        updated=interview.update_requirements(state,values)
        updated['style_recheck']=[]
        commit(state,updated)
    missing=interview.blockers(state)
    if missing:
        st.info('Before confirming: '+text('; '.join(missing)))
    else:
        st.success('The important requirements are present. Review the summary, including any assumptions, then confirm when it matches your intent.')
    st.markdown('**Decisions for confirmation**')
    for key in ('purpose','audience','goals','selected_styles','functionality'):
        st.write('**'+interview.FIELDS[key]+':** '+text(state['requirements'][key]['value'] or 'Not decided'))
    with st.expander('Full project summary and remaining assumptions'):
        st.table([{'Decision':label,'Value':text(state['requirements'][key]['value'] or 'Not specified — use a restrained, accessible choice consistent with the selected style.'),
                   'Status':state['requirements'][key]['status']} for key,label in interview.FIELDS.items()])
    a,b=st.columns(2)
    if a.button('Confirm and generate design brief',type='primary',disabled=bool(missing),help='Resolve the listed questions first.' if missing else 'Confirms the displayed decisions and assembles an editable brief.'):
        commit(state,interview.confirm_summary(state))
    if b.button('Continue refining'):
        updated=deepcopy(state);interview.invalidate(updated);commit(state,updated)
    st.caption('The brief is assembled from these decisions without another model rewrite, so explicit requirements are not silently changed. This step does not generate website code.')


def render_final(state, perform_job):
    if not state['summary_approval']:
        st.info('Complete the interview and confirm the summary in Review decisions. Website generation stays locked until the current brief is approved.')
        return
    st.subheader('Your brief is the source of truth')
    st.caption('Editing is allowed. Review the complete text before approving; website generation receives this exact version, together with the fixed platform constraints.')
    approved=state.get('approved_brief')
    with st.form('final_design_brief_'+str(state['revision'])):
        draft=st.text_area('Editable design brief',value=state['draft_brief'],height=340,max_chars=12000)
        save=st.form_submit_button('Save brief edits')
        if not approved:
            reviewed=st.checkbox('I approve this exact design brief',key='approve_brief_'+interview.digest(state['draft_brief']))
            approve=st.form_submit_button('Approve design brief',type='primary')
            build=False;validation='Runtime errors only'
        else:
            reviewed=approve=False
            validation=st.selectbox('Validation',['Runtime errors only','Counter behaviour + runtime'],key='interview_build_checks')
            st.caption('Counter validation requires Increase, Decrease and Reset controls. Runtime checks alone do not verify every requested feature.')
            build=st.form_submit_button('Build, check and host locally',type='primary')
    if save:commit(state,interview.edit_brief(state,draft))
    if approve:
        if reviewed:commit(state,interview.approve_brief(interview.edit_brief(state,draft)))
        else:st.error('Review the brief and select the approval checkbox before approving.')
    if not approved:
        st.caption('Approval saves the exact text submitted with the checkbox. Website code is not generated at this step.')
    else:
        st.success('Approved. Changing a requirement or the saved brief will require fresh approval.')
    if build:
        if draft.strip()!=state['draft_brief']:
            # Capture edits submitted with Build, revoke old approval, and never build stale text.
            commit(state,interview.edit_brief(state,draft))
        else:
            perform_job({'workflow':'interview_build','interview_id':state['id'],'revision':state['revision'],
                         'approval_hash':approved['hash'],'use_counter_checks':validation=='Counter behaviour + runtime'})
    st.download_button('Download planning brief',state['draft_brief'],file_name='synthetix-design-brief.txt',mime='text/plain')


def render_live_brief(state):
    with st.container(key='interview-live-brief'):
        st.subheader('Shared understanding')
        st.caption('Saved locally · revision '+str(state['revision']))
        for key in ('purpose','audience','goals','selected_styles','functionality'):
            item=state['requirements'][key]
            st.markdown('**'+interview.FIELDS[key]+'**')
            st.write(text(item['value'] or 'Not decided yet'))
            st.caption(item['status'].capitalize())
        missing=interview.blockers(state)
        st.markdown('**Next decisions**')
        if missing:
            for item in missing[:8]:st.write('• '+text(item))
        elif state['approved_brief']:st.write('Approved brief is ready for generation.')
        elif state['summary_approval']:st.write('Review and approve the editable brief.')
        else:st.write('Ready for your summary review.')
        defaults=[interview.FIELDS[k] for k,v in state['requirements'].items() if v['status']=='default']
        if defaults:st.caption('Defaults to review: '+', '.join(defaults))
        if state['build_runs']:st.caption('Generated runs: '+str(len(state['build_runs'])))


def render_interview(perform_job):
    saved=interview.list_interviews()
    with st.expander('Resume a saved design interview'):
        if saved:
            selected=st.selectbox('Saved interview',saved,format_func=lambda value:value['title']+' · '+value['id'][:6])
            if st.button('Resume interview'):
                select_interview(selected['id']);st.rerun()
        else:st.caption('Your first conversation will appear here after you begin.')
    identifier=st.query_params.get('interview') or st.session_state.get('design_interview_id')
    if not identifier:
        render_start(perform_job);return
    try:state=interview.load(identifier)
    except (ValueError,OSError) as error:
        st.error(text(error))
        if st.button('Start a new interview'):
            st.query_params.pop('interview',None);st.session_state.pop('design_interview_id',None);st.rerun()
        return
    select_interview(identifier)
    with st.container(key='interview-heading'):
        head,action=st.columns([3,1])
        with head:
            st.header(interview.stage(state))
            st.caption('Understand → Explore → Define → Review → Generate. Return to any decision without starting over.')
        if action.button('New interview',width='stretch'):
            st.query_params.pop('interview',None);st.session_state.pop('design_interview_id',None);st.rerun()
    left,right=st.columns([2.2,1],gap='large')
    with left,st.container(key='interview-canvas'):
        tabs=st.tabs(['Conversation','Style explorer','Review decisions','Final brief'])
        with tabs[0]:render_conversation(state,perform_job)
        with tabs[1]:render_styles(state)
        with tabs[2]:render_decisions(state)
        with tabs[3]:render_final(state,perform_job)
    with right:render_live_brief(state)
