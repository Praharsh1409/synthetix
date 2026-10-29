"""Run browser and model work outside Streamlit's Windows event loop."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid
import design_interview as interview
from generation_ui import emit_stage

from browser_check import check_html
from counter_check import check_counter
from intent_checks import check_intent
from project_store import source_file, validation_manifest
from hosting import publish_html
from intent_checks import validate_checks
from nebius_tasks import plan_repair, refine_brief
from synthetix import run_pipeline, check_version
from browser_safety import ERROR_KINDS
from artifact_io import write_text, write_json, public_error
from web_documents import assemble_document

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'artifacts'


def safe_folder(raw):
    folder = Path(raw).resolve()
    folder.relative_to(ARTIFACTS.resolve())
    if not folder.name.startswith('synthetix_') or not folder.is_dir():
        raise ValueError('Invalid run folder.')
    return folder




def create_folder(kind):
    folder = ARTIFACTS / ('synthetix_' + kind + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def submitted_document(request):
    return assemble_document(request.get('html', ''), request.get('css', ''), request.get('javascript', ''))


def attach_host(summary, title):
    folder = safe_folder(summary['output_folder'])
    if summary.get('status') == 'no_runtime_errors_observed':
        print('Hosting the checked website locally...', flush=True)
        try:
            summary['local_site'] = publish_html((folder / 'final.html').read_bytes().decode('utf-8'),
                                                 title=title, source=summary.get('initial_source', 'generated'))
            summary.pop('hosting_error', None)
        except Exception as error:
            summary['hosting_error'] = str(error)
        write_json(folder / 'summary.json', summary)
    return summary


def handle(request):
    workflow = request.get('workflow')
    if workflow in ('interview_turn','interview_build'):
        state=interview.load(request.get('interview_id'))
        if request.get('revision')!=state['revision']:
            raise ValueError('The interview changed. Reload before continuing.')
        if workflow=='interview_turn':
            print('Planning the next design decision...',flush=True)
            try:
                updated=interview.respond(state)
                interview.save(updated,expected_revision=state['revision'])
            except Exception as error:
                message=public_error(error)
                try:interview.save(interview.record_failure(state,error),expected_revision=state['revision'])
                except (OSError,ValueError):pass
                return {'ok':False,'kind':'interview','error':message,'interview_id':state['id']}
            return {'ok':True,'kind':'interview','interview_id':state['id']}
        prompt,context=interview.build_spec(state)
        if request.get('approval_hash')!=state['approved_brief']['hash']:
            raise ValueError('The approved brief changed. Review it again before building.')
        counter=request.get('use_counter_checks',False)
        if not isinstance(counter,bool):raise ValueError('Invalid validation selection.')
        emit_stage('brief')
        summary=run_pipeline(prompt,use_counter_checks=counter,workflow_context=context,progress=emit_stage)
        summary=attach_host(summary,'Generated website')
        if summary.get('status')=='no_runtime_errors_observed':emit_stage('preview')
        current=interview.load(state['id'])
        current['build_runs'].append({'folder':summary['output_folder'],'approval_hash':state['approved_brief']['hash'],'at':interview.now()})
        interview.save(current,expected_revision=current['revision'])
        passed=summary.get('status')=='no_runtime_errors_observed'
        return {'ok':passed,'kind':'run','summary':summary,'output_folder':summary['output_folder'],
                **({} if passed else {'error':summary.get('error','Review the saved failure report.')})}

    if workflow == 'refine':
        print('Improving the website brief...', flush=True)
        return {'ok': True, 'kind': 'brief', 'brief': refine_brief(request.get('prompt', ''))}

    if workflow == 'test_saved':
        original = safe_folder(request.get('output_folder', ''))
        source = source_file(original, request.get('version', ''))
        document = source.read_bytes().decode('utf-8')
        manifest=validation_manifest(original)
        checks = validate_checks(manifest.get('intent_checks', []))
        counter_selected = manifest.get('counter_checks_selected') is True
        folder = create_folder('check')
        write_text(folder/'version_0.html',document)
        print('Checking version 0 in Chromium...', flush=True)
        report=check_version(document,f'{folder.name}/preview_0.png',counter_selected,checks)
        errors=report['combined_errors']
        write_json(folder / 'report_0.json', report)
        passed = not any(errors.values())
        if passed:
            write_text(folder/'final.html',document)
        summary = {'status':('execution_failed' if errors['execution_errors'] else 'no_runtime_errors_observed' if passed else 'checks_failed'),
                   'output_folder':str(folder), 'repairs_used':0, 'initial_source':'saved_version_check',
                   'requested_features_verified':False,
                   'counter_behavior_verified':passed and counter_selected,
                   'intent_checks_verified':passed and bool(checks), 'intent_check_steps':len(checks),
                   'checked_from':{'folder':str(original),'version':source.name}}
        write_json(folder / 'summary.json', summary)
        write_json(folder / 'run.json', manifest)
        result = {'ok':passed, 'kind':'run', 'output_folder':str(folder), 'summary':summary}
        if not passed:
            result['error'] = 'Selected checks failed. No AI repair was performed. Review diagnostics or open Repair.'
        return result

    if workflow == 'diagnose':
        document = submitted_document(request)
        folder = create_folder('diagnosis')
        write_text(folder/'version_0.html',document)
        print('Checking your submitted code in Chromium...', flush=True)
        report = check_html(document, f'{folder.name}/preview_0.png')
        report['combined_errors'] = {kind:list(report.get(kind,[])) for kind in ERROR_KINDS}
        write_json(folder / 'report_0.json', report)
        diagnosis = {'folder': str(folder), 'code_hash': hashlib.sha256(document.encode()).hexdigest(),
                     'report': report}
        write_json(folder / 'diagnosis.json', diagnosis)
        write_json(folder / 'summary.json', {'status': 'execution_failed' if report.get('execution_errors') else 'diagnosis_only', 'output_folder': str(folder),
                    'repairs_used': 0, 'requested_features_verified': False, 'initial_source': 'submitted_html'})
        result={'ok':not bool(report.get('execution_errors')),'kind':'diagnosis','diagnosis':diagnosis,'output_folder':str(folder)}
        if not result['ok']:result['error']='Browser inspection could not complete. Review the saved report; no pass is claimed.'
        return result

    if workflow in ('plan_repair', 'repair'):
        folder = safe_folder(request.get('diagnosis_folder', ''))
        document = (folder / 'version_0.html').read_bytes().decode('utf-8')
        purpose = request.get('purpose', '')
        if not isinstance(purpose, str) or not 1 <= len(purpose.strip()) <= 3000:
            raise ValueError('Describe what this code should do before repairing it.')
        if workflow == 'plan_repair':
            print('Planning checks for your intended behaviour...', flush=True)
            report = json.loads((folder / 'report_0.json').read_text(encoding='utf-8'))
            plan = plan_repair(document, purpose, report['combined_errors'])
            return {'ok': True, 'kind': 'repair_plan', 'plan': plan}
        if request.get('checks_reviewed') is not True:
            raise ValueError('Review the proposed behaviour checks before starting repair.')
        checks = validate_checks(request.get('intent_checks', []))
        summary = run_pipeline(
            purpose, initial_html=document, intent_checks=checks,
            force_initial_repair=not bool(checks),
            workflow_context={'workflow': 'repair', 'purpose': purpose, 'diagnosis_folder': str(folder),
                              'approved_checks': checks},
        )
        summary = attach_host(summary, 'Repaired website')

    elif workflow in ('generate', 'build'):
        prompt = request.get('prompt', '')
        checks = request.get('use_counter_checks', False)
        if not isinstance(prompt, str) or not isinstance(checks, bool):
            raise ValueError('Invalid generation request.')
        summary = run_pipeline(prompt, use_counter_checks=checks,
                               workflow_context=request.get('brief_context', {}))
        summary = attach_host(summary, 'Generated website')

    elif workflow == 'demo':
        from demo_self_heal import BROKEN_COUNTER, PROMPT
        summary = run_pipeline(PROMPT, use_counter_checks=True, initial_html=BROKEN_COUNTER,
                               demo_label='Increase adds two instead of one')

    elif workflow == 'host_code':
        document=submitted_document(request)
        folder=create_folder('host')
        write_text(folder/'version_0.html',document)
        summary={'status':'checking','output_folder':str(folder),'repairs_used':0,
                 'requested_features_verified':False,'initial_source':'submitted_unmodified'}
        write_json(folder/'summary.json',summary)
        print('Checking your submitted site before hosting...',flush=True)
        report=check_version(document,f'{folder.name}/preview_0.png')
        write_json(folder/'report_0.json',report)
        if report['combined_errors']['execution_errors']:
            summary.update(status='execution_failed',error='Browser inspection could not complete. The source is saved; hosting was not started.')
        else:
            write_text(folder/'final.html',document)
            print('Hosting your submitted code locally...',flush=True)
            try:
                site=publish_html(document,title=request.get('title','Pasted website'),source='submitted_unmodified')
                summary.update(status='hosted_as_submitted',local_site=site,final_html=str(folder/'final.html'),
                               runtime_errors_observed=bool(report['javascript_errors'] or report['console_errors']))
            except Exception as error:
                summary.update(status='hosting_failed',error=public_error(error))
        write_json(folder/'summary.json',summary)
        result={'ok':summary['status']=='hosted_as_submitted','kind':'host','output_folder':str(folder),'summary':summary}
        if not result['ok']:result['error']=summary['error']
        return result

    elif workflow == 'host_existing':
        folder = safe_folder(request.get('output_folder', ''))
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        if summary.get('status') not in ('no_runtime_errors_observed', 'hosted_as_submitted', 'hosting_failed'):
            raise ValueError('This run does not contain a publishable final document.')
        document = (folder / 'final.html').read_bytes().decode('utf-8')
        summary['local_site'] = publish_html(document, title='Synthetix website', source='saved_run',
                                            site_id=summary.get('local_site', {}).get('site_id'))
        summary.pop('hosting_error', None)
        if summary.get('status')=='hosting_failed':
            summary.update(status='hosted_as_submitted')
            summary.pop('error',None)
        write_json(folder / 'summary.json', summary)
        return {'ok': True, 'kind': 'host', 'output_folder': str(folder), 'summary': summary}
    else:
        raise ValueError('Unknown workflow.')

    passed = summary.get('status') == 'no_runtime_errors_observed'
    result = {'ok': passed, 'kind': 'run', 'output_folder': summary['output_folder'], 'summary': summary}
    if not passed:
        result['error'] = summary.get('error','Review the saved failure report.')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text(encoding='utf-8'))
        result = handle(request)
    except Exception as error:
        status = getattr(error, 'status_code', None)
        if status:
            message = f'The model service returned HTTP {status}. Try again after checking service access and availability.'
        else:
            message = str(error)[:1000]
            secret = os.getenv('NEBIUS_API_KEY', '')
            if secret:
                message = message.replace(secret, '[redacted]')
        result = {'ok': False, 'error': message, 'error_type': type(error).__name__}
    Path(args.result).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
