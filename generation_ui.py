"""Stage-based generation progress and the provided Synthetix loading mark."""
import base64
import json
from pathlib import Path
from runtime_paths import artifacts_dir

import streamlit as st
from text_safety import markdown_text

ROOT = Path(__file__).resolve().parent
PREFIX = 'SYNTHEX_STAGE '
STAGES = [
    ('brief', 'Approved brief loaded'),
    ('generated', 'Website HTML generated'),
    ('checked', 'Browser inspection completed'),
    ('saved', 'Final website saved'),
    ('preview', 'Review preview prepared'),
]


def emit_stage(stage):
    if stage not in dict(STAGES):
        raise ValueError('Unknown website generation stage.')
    print(PREFIX + json.dumps({'stage': stage}), flush=True)


def completed_from_line(line, previous=0):
    """Only explicit worker milestones advance the bar; time never does."""
    if not line.startswith(PREFIX):
        return previous
    try:
        event = json.loads(line[len(PREFIX):])
        index = next(i for i, (key, _) in enumerate(STAGES, 1) if key == event.get('stage'))
    except (ValueError, TypeError, AttributeError, StopIteration):
        return previous
    # 100% is reserved for a successful result AND an actual saved final document.
    if index > previous + 1:
        return previous
    return max(previous, min(index, len(STAGES) - 1))


def successful_result(outcome):
    if not isinstance(outcome, dict) or outcome.get('ok') is not True:
        return False
    try:
        folder = Path(outcome['output_folder']).resolve()
        folder.relative_to(artifacts_dir(ROOT / 'artifacts').resolve())
        final = folder / 'final.html'
        if folder.is_symlink() or final.is_symlink() or not final.is_file() or final.stat().st_size == 0:
            return False
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        report = json.loads((folder / ('report_' + str(summary.get('current_version', 0)) + '.json')).read_text(encoding='utf-8'))
        errors=report.get('combined_errors')
        return (summary.get('status') == 'no_runtime_errors_observed' and report.get('passed') is True
                and isinstance(errors, dict) and all(isinstance(errors.get(kind),list) and not errors[kind]
                    for kind in ('javascript_errors','console_errors','behavior_errors','execution_errors')))
    except (KeyError, OSError, ValueError, TypeError):
        return False


def loader_markup(active=True):
    logo = base64.b64encode((ROOT / 'assets' / 'synthetix-loading-logo.png').read_bytes()).decode('ascii')
    return ('<div class="sx-build-loader ' + ('is-active' if active else 'is-finished') + '" role="img" aria-label="Synthetix">'
            '<span class="sx-build-orbit" aria-hidden="true"></span>'
            '<img src="data:image/png;base64,' + logo + '" alt="" width="88" height="88"></div>')


def saved_review(state):
    approval=state.get('approved_brief')
    if not approval:
        return None
    matching=[run for run in state.get('build_runs',[]) if isinstance(run,dict) and run.get('approval_hash')==approval['hash']]
    if not matching:
        return None
    try:
        folder=Path(matching[-1]['folder']).resolve()
        folder.relative_to(artifacts_dir(ROOT/'artifacts').resolve())
        summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
        outcome={'ok':summary.get('status')=='no_runtime_errors_observed','kind':'run','output_folder':str(folder),'summary':summary}
        if not successful_result(outcome):
            outcome.update(ok=False,error=summary.get('error','This saved build needs review. No completed website is claimed.'))
        return outcome
    except (KeyError,OSError,ValueError,TypeError):
        return {'ok':False,'error':'The saved website could not be reopened. Its files have not been overwritten.'}


def render_generation(job, executor):
    loading_area=st.empty()
    with loading_area.container(), st.container(key='website-generation'):
        logo = st.empty()
        logo.html(loader_markup())
        heading=st.empty()
        heading.subheader('Your website is being prepared')
        st.write('We are building from your approved brief, checking the result in Chromium, and preparing it for review.')
        bar = st.progress(0, text='0% · Starting the approved build')
        st.caption('Progress shows completed workflow stages, not a time estimate. AI generation may remain on one stage while a request is running.')
        milestones = st.empty()
        state = {'completed': 0}

        def show(value):
            state['completed'] = value
            label = STAGES[value - 1][1] if value else 'Starting the approved build'
            bar.progress(value / len(STAGES), text=f'{value * 20}% · {label}')
            rows = [{'Stage': title, 'Status': 'Completed' if i < value else 'Not completed'} for i, (_, title) in enumerate(STAGES)]
            milestones.table(rows)

        show(0)

        def observe(line):
            value = completed_from_line(line, state['completed'])
            if value != state['completed']:
                show(value)

        with st.status('Build activity', expanded=False) as status:
            try:
                outcome = executor(job, status, on_progress=observe)
            except Exception:
                outcome = {'ok': False, 'error': 'The local generation worker could not finish. Your approved brief is still saved.'}
            if not isinstance(outcome,dict):
                outcome={'ok':False,'error':'The worker returned an unreadable result. Your approved brief is still saved.'}
            if successful_result(outcome):
                show(len(STAGES))
                status.update(label='Website generated and ready to review', state='complete', expanded=False)
            else:
                # Do not let a malformed/partial worker success turn into a green completion.
                outcome = {**outcome, 'ok': False, 'error': outcome.get('error', 'The worker did not produce a verified saved website. Review the available evidence or retry.')}
                status.update(label='Website preparation stopped', state='error', expanded=True)
        logo.html(loader_markup(active=False))
        if not outcome.get('ok'):
            heading.subheader('Website preparation stopped')
            st.error(markdown_text(outcome['error']))
            st.caption('The progress bar has stopped at the last completed stage. Existing code and your approved brief were kept.')
    if outcome.get('ok'):
        # Keep the actual website prominent after completion instead of leaving a
        # large loading card above the result and making the preview hard to find.
        loading_area.empty()
        with loading_area.container():
            st.progress(1.0,text='100% · Website generated, checked, saved and ready to review')
    return outcome
