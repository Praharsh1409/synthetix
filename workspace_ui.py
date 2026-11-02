"""Native Streamlit workbench for real saved code, browser evidence, and versions."""
import difflib
import html
import json

import streamlit as st
from text_safety import markdown_text
from browser_safety import ERROR_KINDS
from reporting import report_problem, version_verdict

from hosting import running_host
from runtime_paths import cloud_mode
from intent_checks import describe_check
from project_store import describe_run, list_runs, read_json, rename_run, restore_version


def status_info(status):
    return {
        'no_runtime_errors_observed': ('Selected checks passed', 'success'),
        'hosted_as_submitted': ('Hosted as submitted', 'neutral'),
        'diagnosis_only': ('Runtime inspection', 'neutral'),
        'repair_limit_reached': ('Repair limit reached', 'error'),
        'checks_failed': ('Checks failed', 'error'),
        'restored_unverified': ('Untested draft', 'warning'),
        'execution_failed': ('Browser could not run','warning'),
        'generation_failed': ('Generation failed','error'),
        'repair_failed': ('Repair failed','error'),
        'hosting_failed': ('Hosting failed','error'),
        'save_failed': ('Save failed','error'),
        'generating': ('Generation incomplete','warning'),
        'checking': ('Checks incomplete','warning'),
        'repairing': ('Repair incomplete','warning'),
    }.get(status, ('Review required', 'warning'))


def pill(text, tone='neutral'):
    st.html(f'<span class="status-pill status-{tone}">{html.escape(text)}</span>')


def diagnostics(report, manifest=None):
    if not report:
        st.info('Not run. Run checks to create a report for this version.')
        return
    problem=report_problem(report)
    if problem:
        st.warning('Report unavailable: '+problem)
        return
    errors=report.get('combined_errors',report)
    execution=errors.get('execution_errors',[])
    runtime=list(errors.get('javascript_errors',[]))+list(errors.get('console_errors',[]))
    if execution:
        st.error('Browser execution could not complete. No runtime pass is claimed.')
        for error in execution:st.code(str(error),language='text')
    if runtime:
        st.error(f'{len(runtime)} runtime issue(s) observed')
        for index,error in enumerate(runtime,1):
            with st.expander(f'Runtime failure {index} · evidence'):
                st.code(str(error),language='text')
    elif not execution:
        st.success('Runtime: no JavaScript or console errors observed.')
    tests=[(key,report[key]) for key in ('counter_check','intent_check') if isinstance(report.get(key),dict)]
    if not tests:
        st.info('Behaviour tests: not selected. A runtime pass does not verify your intended behaviour.')
    for key,test in tests:
        if test.get('skipped'):
            st.warning('Behaviour tests could not run: '+test.get('reason','Resolve execution errors first.'))
            continue
        for check in test.get('checks_passed',[]):st.write('Passed · '+markdown_text(check))
        failures=test.get('behavior_errors',[])
        for error in failures:
            if isinstance(error,dict):
                st.error('Failed · '+markdown_text(error.get('step','Behaviour check')))
                with st.expander('Failure evidence'):
                    st.code(str(error.get('details',error)),language='text')
            else:st.error('Failed · '+markdown_text(error))
        pending=test.get('checks_not_run')
        if pending is None and failures and key=='intent_check' and manifest:
            start=len(test.get('checks_passed',[]))+(0 if any(isinstance(e,dict) and e.get('step')=='Load page' for e in failures) else 1)
            pending=[describe_check(check) for check in manifest.get('intent_checks',[])[start:]]
        for check in pending or []:st.write('Not run · '+markdown_text(check))
        if test.get('passed') and not any(test.get(kind) for kind in ERROR_KINDS):
            st.success('The selected behaviour checks passed.')
    st.caption('Manual review: appearance, accessibility, mobile layout, and other interactions are not established by these checks.')


def render_workspace(folder, perform_job, preview_document, pages):
    item = describe_run(folder)
    summary, files = item['summary'], item['versions']
    if summary.get('error'):st.error(markdown_text(summary['error']))
    if summary.get('_read_error'):st.warning(summary['_read_error'])
    if not files:
        st.warning('This run has no saved HTML. Start a new build or import a page.')
        return
    with st.container(key='workbench'):
        stages = ['Plan', 'Generate', 'Test', 'Repair', 'Retest', 'Review']
        completed = set()
        if item['manifest'].get('approved_brief'): completed.add('Plan')
        if item['mode'] == 'Build': completed.add('Generate')
        if any((item['folder'] / f'report_{int(file.stem.split("_")[-1])}.json').exists() for file in files): completed.add('Test')
        if summary.get('repairs_used', 0): completed.add('Repair')
        if summary.get('repairs_used', 0) and len(files) > 1: completed.add('Retest')
        st.html('<div class="stage-track" aria-label="Workflow evidence">'+''.join('<span class="'+('stage-active' if stage=='Review' else 'stage-complete' if stage in completed else '')+'">'+stage+(' · current' if stage=='Review' else ' · recorded' if stage in completed else ' · not recorded')+'</span>' for stage in stages)+'</div>')
        head, state = st.columns([3, 1])
        with head:
            st.header(markdown_text(item['title']))
            st.caption(f"{item['mode']} · Saved {item['created']:%d %b %Y, %H:%M} · {len(files)} HTML version(s)")
        with state:
            version_state = st.empty()
        with st.container(key='workbench-controls'):
            version_col, view_col, export_col = st.columns([2, 2, 1.3])
            with version_col:
                selected = st.selectbox('Version', files, index=len(files)-1,
                                        format_func=lambda p: 'Version ' + p.stem.split('_')[-1] + (' · latest' if p == files[-1] else ' · historical'), key='wb_version_' + item['folder'].name)
            with view_col:
                layout = st.selectbox('Panel layout', ['Studio workspace', 'Tabbed workspace', 'Split workspace', 'Preview focus', 'Code focus'], key='wb_layout')
            document = selected.read_text(encoding='utf-8')
            number = int(selected.stem.split('_')[-1])
            report = read_json(item['folder'] / f'report_{number}.json')
            version_label,tone=version_verdict(report)
            with version_state.container():
                pill(f'Version {number} · {version_label}', tone)
            with export_col:
                st.caption('Single HTML file · selected version')
                st.download_button('Download HTML', selected.read_bytes(), file_name=f'synthetix-v{number}.html', mime='text/html', width='stretch', key='export_' + item['folder'].name)
        with st.container(key='workbench-actions', horizontal=True):
            if st.button('Run checks', type='primary', help='Recheck this saved version with the originally selected behaviour tests. No model call.'):
                result = perform_job({'workflow': 'test_saved', 'output_folder': str(item['folder']), 'version': selected.name})
                if result.get('output_folder'):
                    st.rerun()
            if st.button('Repair code', help='Open this source in the guided Repair workflow; no automatic model call.'):
                st.session_state['pending_repair_code'] = document
                st.switch_page(pages['repair'])
            if st.button('Restore as new draft', help='Create an untested draft from this version. Earlier code and reports remain intact.'):
                try:
                    draft=restore_version(item['folder'],selected.name)
                    st.session_state['run_folder']=str(draft)
                    st.rerun()
                except (OSError,ValueError) as error:
                    st.error('The draft could not be saved. Earlier versions remain unchanged. '+str(error))
        if summary.get('demo_label'):
            st.caption('Controlled demo · The starting bug was deliberately supplied: ' + summary['demo_label'])
        if summary.get('restored_from'):
            st.info('Restored as an untested draft. Run checks before trusting this version.')
        if item['status'] == 'hosted_as_submitted':
            st.caption('Hosted without AI edits. Hosting is not a correctness claim.')
        if layout == 'Split workspace':
            left, right = st.columns([1, 2], gap='medium')
        else:
            left = right = None

        def code_panel():
            with st.container(border=True, key='source-panel'):
                st.subheader('Source code')
                st.caption('Editable draft · kept in this session after leaving the field. Inspect edited code saves a new run; saved versions remain unchanged.')
                with st.expander('Read-only source · syntax highlighted'):
                    st.code(document, language='html', line_numbers=True)
                edited = st.text_area('HTML source', value=document, height=390, max_chars=100000, persist_state='session',
                                      key='source_' + item['folder'].name + '_' + str(number))
                if edited != document:
                    st.info('Session draft differs from this saved version. Inspect to save and test it. Download HTML still exports the selected saved version.')
                inspect = st.button('Inspect edited code', key='inspect_source_'+item['folder'].name+'_'+str(number))
                if inspect:
                    result = perform_job({'workflow':'diagnose', 'html':edited, 'css':'', 'javascript':''})
                    if result.get('ok'):
                        st.rerun()

        def preview_panel():
            with st.container(border=True, key='preview-panel'):
                st.subheader('Browser preview')
                st.caption(f'Version {number} · Interactive sandbox · No external network access')
                if st.button('Refresh preview', key='refresh_'+item['folder'].name):
                    st.session_state['preview_refresh']=st.session_state.get('preview_refresh',0)+1
                if not report or report_problem(report) or report.get('combined_errors',report).get('execution_errors'):
                    st.info('Preview not started: this version needs a completed browser inspection. Review the source and run checks first.')
                else:
                    device = st.radio('Preview viewport', ['Fit', 'Desktop · 1280px', 'Tablet · 768px', 'Mobile · 390px'], horizontal=True, key='device_'+item['folder'].name)
                    widths = {'Fit': '100%', 'Desktop · 1280px': '1280px', 'Tablet · 768px': '768px', 'Mobile · 390px': '390px'}
                    st.caption('Fixed widths scroll inside the preview when wider than this panel. Fit follows the panel width.')
                    from web_documents import preview_frame_html
                    markup = preview_frame_html(document, 'Synthetix version '+str(number)+' preview '+str(st.session_state.get('preview_refresh',0)))
                    st.markdown('<div style="max-width:100%;overflow-x:auto"><div style="width:'+widths[device]+'">'+markup+'</div></div>', unsafe_allow_html=True)

        primary_tabs = None
        if layout == 'Studio workspace':
            task, canvas = st.columns([1, 2.7], gap='medium')
            with task, st.container(key='task-rail'):
                st.subheader('Review this version')
                st.caption(f'Version {number} · {selected.name}')
                pill(version_label, tone)
                st.write('Try the preview, review the evidence, then keep or revise your code.')
                st.caption(f"Recorded AI repairs: {summary.get('repairs_used', 0)}. Automatic repair runs are limited to three attempts.")
                with st.expander('Available checks', expanded=True):
                    if item['manifest'].get('intent_checks'):
                        for check in item['manifest']['intent_checks']: st.write(markdown_text(describe_check(check)))
                    else: st.caption('No custom behaviour tests recorded. Runtime checks alone do not test intent.')
            with canvas:
                primary_tabs = st.tabs(['Preview', 'Code', 'Checks', 'Versions'])
                with primary_tabs[0]: preview_panel()
                with primary_tabs[1]: code_panel()
        elif layout == 'Tabbed workspace':
            primary_tabs = st.tabs(['Preview', 'Code', 'Checks', 'Versions'])
            with primary_tabs[0]: preview_panel()
            with primary_tabs[1]: code_panel()
        elif left is not None:
            with left: code_panel()
            with right: preview_panel()
        elif layout == 'Preview focus':
            preview_panel()
            with st.expander('Source editor'): code_panel()
        else:
            code_panel()
            with st.expander('Browser preview'): preview_panel()

        tabs = st.tabs(['Checks', 'Versions', 'Repair activity', 'Screenshot & reports']) if primary_tabs is None else [primary_tabs[2], primary_tabs[3], st.expander('Repair activity'), st.expander('Screenshot & reports')]
        with tabs[0]:
            diagnostics(report, item['manifest'])
        with tabs[1]:
            st.caption('Choose a saved version above to inspect it. Restore creates a new, untested draft.')
            for version_file in files:
                version_number = int(version_file.stem.split('_')[-1])
                thumbnail = item['folder'] / f'preview_{version_number}.png'
                if thumbnail.is_file():
                    with st.expander(f'Version {version_number} · captured preview'):
                        st.image(str(thumbnail), width='stretch')
            baseline = st.selectbox('Compare against', files, format_func=lambda p: 'Version ' + p.stem.split('_')[-1], key='baseline_' + item['folder'].name)
            diff = ''.join(difflib.unified_diff(baseline.read_text(encoding='utf-8').splitlines(keepends=True),
                                               document.splitlines(keepends=True), fromfile=baseline.name, tofile=selected.name))
            st.caption('Comparing '+baseline.name+' → '+selected.name)
            st.code(diff or 'No source differences between the selected versions.', language='diff')
            with st.expander('Rendered comparison · saved screenshots'):
                before, after = st.columns(2)
                for column, version in [(before,baseline),(after,selected)]:
                    index = int(version.stem.split('_')[-1])
                    picture = item['folder']/f'preview_{index}.png'
                    with column:
                        st.caption(version.name)
                        if picture.is_file():st.image(str(picture),width='stretch')
                        else:st.info('No recorded screenshot for this version.')
        with tabs[2]:
            st.write('Saved evidence for each attempt')
            for file in files:
                idx = int(file.stem.split('_')[-1])
                evidence = read_json(item['folder'] / f'report_{idx}.json')
                issues = evidence.get('combined_errors', {})
                count = sum(len(issues.get(key, [])) for key in ['javascript_errors','console_errors','behavior_errors'])
                verdict,_=version_verdict(evidence)
                st.write(f'Version {idx} · {verdict}')
            st.caption(f"AI repairs used in this run: {summary.get('repairs_used', 0)}")
        with tabs[3]:
            screenshot = item['folder'] / f'preview_{number}.png'
            if screenshot.is_file():
                st.image(str(screenshot), caption=f'Chromium screenshot captured while checking version {number}.', width='stretch')
            else:
                st.info('No screenshot yet for this version.')
            with st.expander('Raw browser report'): st.json(report or {'status':'not_run'})
            st.download_button('Download run summary', json.dumps(summary, indent=2), file_name='summary.json', mime='application/json', key='summary_' + item['folder'].name)
        with st.expander('Project settings'):
            with st.form('rename_' + item['folder'].name):
                title = st.text_input('Project name', value=item['title'], max_chars=120)
                if st.form_submit_button('Save name'):
                    try: rename_run(item['folder'], title); st.rerun()
                    except (ValueError,OSError) as error: st.error('The project name could not be saved: '+str(error))
        if summary.get('hosting_error'):
            st.warning('Local hosting could not start: ' + markdown_text(summary['hosting_error']))
        site = summary.get('local_site') or {}
        host = running_host()
        if cloud_mode():
            st.caption('This page is running in the isolated preview above. Download HTML to keep it or run it on your own computer. The hosted server does not publish links to your localhost.')
        elif host and f':{host["port"]}/' in site.get('url',''):
            st.link_button('Open locally hosted website', site['url'])
        elif item['status'] in ('no_runtime_errors_observed','hosted_as_submitted','hosting_failed'):
            if st.button('Start local hosting', key='host_' + item['folder'].name):
                result = perform_job({'workflow':'host_existing','output_folder':str(item['folder'])})
                if result.get('ok'): st.rerun()


def render_dashboard(pages):
    runs = list_runs()
    st.title('Your workspace')
    st.write('Welcome to Synthetix. Start with an idea, or pick up where your last run ended.')
    big, small = st.columns([1.7, 1], gap='medium')
    with big:
        with st.container(border=True, key='dashboard-primary'):
            st.header('What will you build next?')
            st.write('Turn a description into a reviewed brief, a working interface, and browser evidence you can inspect.')
            if st.button('New project', type='primary'):
                st.session_state.pop('run_folder', None)
                st.session_state.pop('design_plan', None)
                st.session_state.pop('design_interview_id', None)
                st.query_params.pop('interview',None)
                st.switch_page(pages['build'])
            st.caption('HTML · CSS · JavaScript')
    with small:
        with st.container(border=True, key='dashboard-repair'):
            st.subheader('Bring your code')
            st.write('Find browser errors and verify the behaviour that matters.')
            st.page_link(pages['repair'], label='Repair existing code')
        with st.container(border=True, key='dashboard-host'):
            st.page_link(pages['host'], label='Run HTML' if cloud_mode() else 'Run locally')
            st.caption('Open your own webpage without AI changes.')
    recent, activity = st.columns([1.7, 1], gap='medium')
    with recent:
        with st.container(border=True, key='recent-runs'):
            st.header('Recent projects')
            st.caption('Saved runs in this temporary visitor session.' if cloud_mode() else 'Saved runs on this computer. Each opens with its source and browser evidence.')
            if not runs:
                st.info('No saved projects yet. Build a website or import code to get started.')
            for item in runs[:5]:
                title_col, action_col = st.columns([4, 1])
                with title_col:
                    st.write('**'+markdown_text(item['title'])+'**')
                    label, _ = status_info(item['status'])
                    st.caption(f"{item['mode']} · {item['created']:%d %b, %H:%M} · {label}")
                with action_col:
                    if st.button('Open', key='open_' + item['folder'].name, help='Open '+markdown_text(item['title'])):
                        st.session_state['run_folder'] = str(item['folder'])
                        st.switch_page(pages['workspace'])
    with activity:
        with st.container(border=True, key='activity-panel'):
            st.header('Latest evidence')
            if runs:
                latest = runs[0]
                label, tone = status_info(latest['status'])
                pill(label, tone)
                st.write(markdown_text(latest['title']))
                st.caption(f"{len(latest['versions'])} saved HTML version(s) · {latest['summary'].get('repairs_used',0)} AI repair(s)")
                if st.button('Open latest workspace'):
                    st.session_state['run_folder'] = str(latest['folder'])
                    st.switch_page(pages['workspace'])
            else:
                st.write('Your first browser report will appear after a run.')
            st.caption('A runtime pass does not establish all requested behaviour. Review selected tests and manual checks.')
