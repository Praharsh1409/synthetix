"""Local Streamlit interface for Synthetix's existing repair pipeline."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import streamlit as st
from text_safety import markdown_text
from ui_design import apply_design, render_home, install_scroll_motion
from hosting import running_host, stop_host
from intent_checks import describe_check, validate_checks
from web_documents import assemble_document, preview_frame_html
from project_store import list_runs
from workspace_ui import render_workspace, render_dashboard
from interview_ui import render_interview
from generation_ui import render_generation, saved_review
import design_interview as design_interview
import guided_interview as guided_interview


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'artifacts'
COUNTER_PROMPT = (
    'Build a dark-themed counter starting at zero. Include buttons named '
    'Increase, Decrease, and Reset. Increase adds one, Decrease subtracts '
    'one, and Reset returns to zero. Use purple accents.'
)
PRICING_PROMPT = (
    'Build a responsive pricing table with Starter, Pro, and Enterprise plans. '
    'Use a dark background, purple accents, clear prices, feature lists, '
    'and a visually highlighted Pro plan. Use text-only content.'
)

st.set_page_config(page_title='Synthetix', page_icon='S', layout='wide', initial_sidebar_state='auto')
apply_design()
if 'pending_repair_code' in st.session_state:
    st.session_state['repair_html'] = st.session_state.pop('pending_repair_code')
    st.session_state['repair_css'] = ''
    st.session_state['repair_js'] = ''
    st.session_state.pop('diagnosis', None)
    st.session_state.pop('repair_plan', None)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def artifact_path(raw):
    """Only display files inside this project's artifacts directory."""
    path = Path(raw).resolve()
    path.relative_to(ARTIFACTS.resolve())
    return path


def preview_document(document, title):
    # The trusted outer frame also blocks child document navigation to the network.
    st.markdown(preview_frame_html(document, title), unsafe_allow_html=True)


def execute_job(job, status, on_progress=None):
    folder = ARTIFACTS / 'ui_jobs' / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    request_file = folder / 'request.json'
    result_file = folder / 'result.json'
    request_file.write_text(json.dumps(job), encoding='utf-8')
    environment = os.environ.copy()
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    process = subprocess.Popen(
        [sys.executable, '-u', str(ROOT / 'ui_worker.py'),
         '--request', str(request_file), '--result', str(result_file)],
        cwd=str(ROOT), env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    lines = []
    try:
        for line in process.stdout:
            line = line.rstrip()
            lines.append(line)
            if on_progress:on_progress(line)
            if line.startswith(('Generating', 'Checking version', 'Running counter',
                                'Asking Nemotron', 'CONTROLLED DEMO', 'PASS:', 'Improving', 'Planning', 'Hosting', 'Checking your')):
                status.write(markdown_text(line))
        process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        process.stdout.close()
    (folder / 'worker.log').write_text('\n'.join(lines), encoding='utf-8')
    if not result_file.exists():
        return {'ok': False, 'error': 'The worker stopped before returning a result. Check the terminal.'}
    return read_json(result_file)


with st.sidebar:
    st.html('<div class="brand"><span class="brand-mark" aria-hidden="true">S</span>Synthetix</div><p class="sidebar-description">AI development workspace</p>')
    navigation_slot = st.container()
    with st.expander('Saved projects'):
        saved_runs = list_runs()
        if saved_runs:
            selected_saved = st.selectbox('Saved run', saved_runs, format_func=lambda item: item['title'][:42])
            if st.button('Load saved run', width='stretch'):
                st.session_state['run_folder'] = str(selected_saved['folder'])
                st.session_state['open_saved_run'] = True
        else:
            st.caption('Your completed runs will appear here.')
    st.caption('NVIDIA Nemotron through Nebius Token Factory')
    st.caption('AI actions use Nebius credits. Local inspection and hosting do not.')
    if running_host():
        with st.expander('Local server is running'):
            st.caption('Stopping the server closes all local site links. Saved files remain.')
            if st.button('Stop local site server'):
                try:
                    if stop_host():st.success('Local site server stopped.')
                    else:st.error('The local server did not confirm shutdown. It may still be running.')
                except OSError:
                    st.error('Shutdown could not be confirmed. Check the local server before retrying.')


def announce_workflow(message):
    st.html('<span hidden data-workflow-announcement="' + html.escape(message, quote=True) + '"></span>')


def perform_job(job):
    announce_workflow('Working. Browser checks and model calls can take a few minutes.')
    with st.status('Working — browser checks and model calls can take a few minutes.', expanded=True) as status:
        try:
            outcome = execute_job(job, status)
        except Exception:
            outcome = {'ok': False, 'error': 'The local worker could not finish. Check the terminal and try again.'}
        if outcome.get('output_folder'):
            st.session_state['run_folder'] = outcome['output_folder']
        if outcome.get('ok'):
            label = {'brief': 'Brief ready to review.', 'diagnosis': 'Code checked. Tell us its purpose next.',
                     'repair_plan': 'Repair plan ready to review.', 'host': 'Local website is ready.',
                     'interview': 'Design conversation saved.', 'run': 'Selected checks passed.'}.get(outcome.get('kind'), 'Done.')
            status.update(label=label, state='complete', expanded=False)
        else:
            status.update(label='The task did not finish successfully.', state='error', expanded=True)
    announce_workflow(label if outcome.get('ok') else 'The task did not finish successfully. Review the error message.')
    if not outcome.get('ok'):
        st.error(markdown_text(outcome.get('error','Review the saved reports.')))
    if outcome.get('output_folder') and job.get('workflow') in ('build','generate','interview_build','repair','demo','host_code'):
        st.switch_page(pages['workspace'])
    return outcome


def open_website_review(job):
    st.session_state['website_review_request'] = job
    st.session_state['website_review_last_request'] = job
    st.session_state.pop('website_review_outcome', None)
    st.session_state['wb_layout'] = 'Preview focus'
    st.switch_page(pages['review'])


def code_editor(prefix):
    uploaded = st.file_uploader('Upload an HTML file (optional)', type=['html', 'htm'], key=prefix + '_upload', max_upload_size=1)
    if uploaded:
        digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
        identity=getattr(uploaded,'file_id',digest)
        if st.session_state.get(prefix + '_uploaded_hash') != digest or st.session_state.get(prefix + '_uploaded_id') != identity:
            try:
                uploaded_text=uploaded.getvalue().decode('utf-8-sig')
                if len(uploaded_text)>100000:
                    raise ValueError('Keep uploaded HTML under 100,000 characters.')
                st.session_state[prefix + '_html'] = uploaded_text
                st.session_state[prefix + '_uploaded_hash'] = digest
                st.session_state[prefix + '_uploaded_id'] = identity
            except UnicodeDecodeError:
                st.error('Please upload an HTML file saved as UTF-8.')
            except ValueError as error:
                st.error(markdown_text(str(error)))
    markup = st.text_area('HTML', height=220, max_chars=100000, key=prefix + '_html',
                          placeholder='Paste a complete HTML page or an HTML fragment.')
    with st.expander('Separate CSS and JavaScript (optional)'):
        css = st.text_area('CSS', height=150, max_chars=100000, key=prefix + '_css')
        javascript = st.text_area('JavaScript', height=150, max_chars=100000, key=prefix + '_js')
    return {'html': markup, 'css': css, 'javascript': javascript}


def render_workflow(workflow):
    if workflow == 'Build a website':
        render_interview(perform_job, open_website_review)

    elif workflow == 'Repair code':
        st.header('First, check the code you have')
        st.caption('Use a self-contained HTML/CSS/JavaScript page. Runtime diagnosis is local. '
                   'Planning and repair send the submitted code and purpose to Nebius.')
        code = code_editor('repair')
        try:
            document = assemble_document(code['html'], code['css'], code['javascript'])
            current_hash = hashlib.sha256(document.encode()).hexdigest()
        except ValueError:
            document = None
            current_hash = None
        if st.button('Find errors', type='primary'):
            outcome = perform_job({'workflow': 'diagnose', **code})
            if outcome.get('ok'):
                st.session_state['diagnosis'] = outcome['diagnosis']
                st.session_state.pop('repair_plan', None)
        diagnosis = st.session_state.get('diagnosis')
        if diagnosis and diagnosis.get('code_hash') == current_hash:
            errors = diagnosis['report']['combined_errors']
            if any(errors.values()):
                st.warning('The browser observed these errors:')
                st.json(errors)
            else:
                st.info('No load-time errors were observed. Intended behaviour still needs to be checked.')
            st.markdown('### What is this code supposed to do?')
            purpose = st.text_area('Describe the intended behaviour', max_chars=3000, height=120, key='repair_purpose',
                                   placeholder='For example: Increase should add exactly one; Reset should show zero.')
            signature = hashlib.sha256((current_hash + purpose).encode()).hexdigest()
            if st.button('Prepare purpose-based repair plan', disabled=not purpose.strip(), help='Describe the intended behaviour first. Planning uses Nebius credits.'):
                outcome = perform_job({'workflow': 'plan_repair', 'diagnosis_folder': diagnosis['folder'], 'purpose': purpose})
                if outcome.get('ok'):
                    st.session_state['repair_plan'] = outcome['plan']
                    st.session_state['repair_plan_signature'] = signature
                    st.session_state['approved_checks_json'] = json.dumps(outcome['plan']['checks'], indent=2)
            plan = st.session_state.get('repair_plan')
            if plan and st.session_state.get('repair_plan_signature') == signature:
                st.markdown('**Understanding of the intended behaviour**')
                st.write(markdown_text(plan['understanding']))
                for issue in plan.get('likely_issues', []):
                    st.write('• Proposed issue: '+markdown_text(issue))
                for assumption in plan.get('assumptions', []):
                    st.write('• Assumption: '+markdown_text(assumption))
                st.markdown('**Proposed behaviour checks**')
                for step in plan.get('checks', []):
                    st.write('• '+markdown_text(describe_check(step)))
                with st.expander('Edit the browser check steps (JSON)'):
                    checks_text = st.text_area('Approved browser steps', key='approved_checks_json', height=240)
                    st.caption('Supported actions: click, fill, expect_text, expect_value, expect_visible. '
                               'Use [] if only purpose-guided repair and runtime checking are appropriate.')
                try:
                    approved_checks = validate_checks(json.loads(checks_text))
                    valid_checks = True
                except (ValueError, json.JSONDecodeError) as error:
                    st.error(markdown_text(str(error)))
                    approved_checks = []
                    valid_checks = False
                st.markdown('**Checks to approve**')
                for check in approved_checks:
                    st.write('• '+markdown_text(describe_check(check)))
                if not approved_checks:
                    st.caption('No behaviour assertions selected. Repair will be guided by your purpose and checked for runtime errors only.')
                reviewed_key = 'reviewed_' + hashlib.sha256((signature + json.dumps(approved_checks, sort_keys=True)).encode()).hexdigest()
                reviewed = st.checkbox('These checks match my intended behaviour', key=reviewed_key)
                if st.button('Repair, verify and host locally', type='primary', disabled=not (reviewed and valid_checks), help='Approve valid behaviour checks above before starting a repair.'):
                    perform_job({'workflow': 'repair', 'diagnosis_folder': diagnosis['folder'], 'purpose': purpose,
                                 'intent_checks': approved_checks, 'checks_reviewed': True})
            elif plan:
                st.info('The purpose has changed. Prepare a new matching repair plan.')
        elif diagnosis:
            st.info('The code has changed. Click Find errors again before requesting repair.')

    elif workflow == 'Host your code':
        st.header('Publish your code on this computer')
        st.caption('Paste a self-contained HTML/CSS/JavaScript page. This workflow makes no model calls '
                   'and does not change your code. The URL is local to this computer.')
        title = st.text_input('Site name', value='My website', max_chars=120)
        code = code_editor('host')
        if st.button('Check and host locally', type='primary'):
            perform_job({'workflow': 'host_code', 'title': title, **code})

    else:
        st.info('This demo deliberately starts with an Increase button that adds two instead of one. '
                'The same repair pipeline must detect the failed check and ask Nemotron to repair it.')
        if st.button('Run controlled repair demo', type='primary'):
            perform_job({'workflow': 'demo'})


def render_saved_result():
    folder = st.session_state.get('run_folder')
    if folder:
        try:
            render_workspace(folder, perform_job, preview_document, pages)
        except (ValueError, OSError, json.JSONDecodeError) as error:
            st.error('This saved run could not be opened: ' + str(error))
    else:
        st.info('Your workspace is ready. Build a website or import code to create the first run.')
        a, b = st.columns(2)
        with a: st.page_link(pages['build'], label='Start building')
        with b: st.page_link(pages['repair'], label='Import code for repair')


def feature_page(workflow, title, description):
    st.set_page_config(page_title=title + ' · Synthetix')
    st.title(title)
    st.write(description)
    steps = {
        'Build a website': ['Understand the idea', 'Choose a direction', 'Approve the brief', 'Build and inspect'],
        'Repair code': ['Import and inspect', 'Explain the purpose', 'Approve tests', 'Repair and compare'],
        'Host your code': ['Submit your page', 'Inspect and open locally'],
        'Controlled repair demo': ['Start with a seeded bug', 'Watch the real repair loop'],
    }.get(workflow, [])
    st.html('<ol class="workflow-guide" aria-label="Workflow steps">' + ''.join(
        '<li><span aria-hidden="true">' + str(i) + '</span>' + html.escape(step) + '</li>'
        for i, step in enumerate(steps, 1)) + '</ol>')
    render_workflow(workflow)
    if st.session_state.get('run_folder'):
        st.page_link(pages['workspace'], label='Open current workspace')


def home_page():
    st.set_page_config(page_title='Synthetix · Browser-tested interfaces')
    render_home(pages)


def build_page():
    feature_page('Build a website', 'Build a website',
                 'Plan with your AI design partner. Compare styles, confirm the decisions, then build.')


def repair_page():
    feature_page('Repair code', 'Repair code',
                 'Check a page, explain its intended behaviour, and review the repair plan.')


def host_page():
    feature_page('Host your code', 'Run locally',
                 'Open your HTML, CSS, and JavaScript on this computer without AI edits.')


def demo_page():
    feature_page('Controlled repair demo', 'Repair demo',
                 'Detect and repair a deliberately seeded counter bug with the full pipeline.')


def dashboard_page():
    st.set_page_config(page_title='Dashboard · Synthetix')
    render_dashboard(pages)


def workspace_page():
    st.set_page_config(page_title='Workspace · Synthetix')
    st.title('Project workspace')
    st.caption('Inspect the source. Try the preview. Follow the evidence.')
    render_saved_result()


def website_review_page():
    st.set_page_config(page_title='Review the website · Synthetix')
    st.title('Review the website')
    if 'wb_layout' not in st.session_state:
        st.session_state['wb_layout'] = 'Preview focus'
    request = st.session_state.pop('website_review_request', None)
    if request is not None:
        st.query_params['interview'] = request['interview_id']
        st.session_state['website_review_last_request'] = request
        outcome = render_generation(request, execute_job)
        st.session_state['website_review_outcome'] = outcome
        if outcome.get('output_folder'):
            st.session_state['run_folder'] = outcome['output_folder']
    else:
        outcome = st.session_state.get('website_review_outcome')
        identifier=st.query_params.get('interview') or st.session_state.get('design_interview_id')
        if outcome is None and identifier:
            try:
                outcome=saved_review(design_interview.load(identifier))
                if outcome is not None:
                    st.session_state['website_review_outcome']=outcome
                    if outcome.get('output_folder'):st.session_state['run_folder']=outcome['output_folder']
            except (OSError,ValueError) as error:
                st.error(markdown_text(str(error)))
    if outcome is not None:
        if outcome.get('ok'):
            st.success('Your website is ready to review.')
            st.caption('Try the preview and inspect the diagnostics. A runtime pass does not verify every requested interaction or the visual design.')
        else:
            if request is None:
                st.error(markdown_text(outcome.get('error', 'Website preparation did not finish.')))
            prior = st.session_state.get('website_review_last_request')
            if prior and st.button('Retry website generation', type='primary'):
                try:
                    state = design_interview.load(prior['interview_id'])
                    if not state.get('approved_brief') or state['approved_brief']['hash'] != prior['approval_hash']:
                        raise ValueError('The brief changed. Review and approve it again before retrying.')
                    open_website_review(guided_interview.build_request(state, prior.get('use_counter_checks', False)))
                except (OSError, ValueError) as error:
                    st.error(markdown_text(str(error)))
        if outcome.get('output_folder'):
            render_saved_result()
    elif st.session_state.get('run_folder'):
        st.caption('Open the preview, inspect its evidence, and download the HTML when you are ready.')
        render_saved_result()
    else:
        st.info('Approve a website brief in Build a website. Generation will start here automatically, then the preview and reports will appear.')
        st.page_link(pages['build'], label='Plan a website')


pages = {
    'home': st.Page(home_page, title='Home', default=True),
    'dashboard': st.Page(dashboard_page, title='Dashboard', url_path='dashboard'),
    'build': st.Page(build_page, title='Build a website', url_path='build'),
    'review': st.Page(website_review_page, title='Review the website', url_path='review'),
    'repair': st.Page(repair_page, title='Repair code', url_path='repair'),
    'host': st.Page(host_page, title='Run locally', url_path='host'),
    'workspace': st.Page(workspace_page, title='Workspace', url_path='workspace'),
    'demo': st.Page(demo_page, title='Repair demo', url_path='demo'),
}
navigation = st.navigation(list(pages.values()), position='hidden')
with navigation_slot:
    for key in ['dashboard','build','review','repair','host','workspace']:
        st.page_link(pages[key], width='stretch')
    st.caption('Explore')
    for key in ['home','demo']:
        st.page_link(pages[key], width='stretch')
if st.session_state.pop('open_saved_run', False):
    st.switch_page(pages['workspace'])
navigation.run()
install_scroll_motion()
