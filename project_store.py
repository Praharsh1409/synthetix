"""Saved-run metadata and non-destructive drafts; no model or browser execution."""
from datetime import datetime
import html
import json
from pathlib import Path
from runtime_paths import artifacts_dir, cloud_mode
import re
import uuid
from artifact_io import write_text, write_json

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'artifacts'


def read_json(path, default=None):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value,dict):
            return {'_read_error':'Saved JSON must contain an object.'}
        return value
    except FileNotFoundError:
        return {} if default is None else default
    except (OSError,ValueError) as error:
        return {'_read_error':'Saved JSON could not be read: '+type(error).__name__}


def safe_run(raw):
    folder = Path(raw).resolve()
    folder.relative_to(artifacts_dir(ARTIFACTS).resolve())
    if not folder.name.startswith('synthetix_') or not folder.is_dir():
        raise ValueError('Choose a saved Synthetix run.')
    return folder


def versions(folder):
    folder = safe_run(folder)
    found=[]
    for path in folder.glob('version_*.html'):
        try:found.append(source_file(folder,path.name))
        except (OSError,ValueError):continue
    return sorted(found,key=lambda path:int(path.stem.split('_')[-1]))


def source_file(folder, name):
    folder = safe_run(folder)
    if not isinstance(name, str) or not re.fullmatch(r'version_\d+\.html', name):
        raise ValueError('Choose an HTML version from this run.')
    file = (folder / name).resolve()
    file.relative_to(folder)
    if not file.is_file():
        raise ValueError('The selected version is unavailable.')
    return file


def describe_run(folder):
    folder = safe_run(folder)
    summary = read_json(folder / 'summary.json')
    manifest = read_json(folder / 'run.json')
    metadata = read_json(folder / 'project.json')
    files = versions(folder)
    context = manifest.get('workflow_context') or {}
    prompt = ''
    try:
        prompt = (folder / 'prompt.txt').read_text(encoding='utf-8').strip()
    except OSError:
        pass
    status = summary.get('status', 'unavailable')
    mode = (('Run HTML' if cloud_mode() else 'Run locally') if status == 'hosted_as_submitted' else
            'Draft' if status == 'restored_unverified' else
            'Repair' if context.get('workflow') == 'repair' else
            'Demo' if summary.get('demo_label') else
            'Inspect' if status == 'diagnosis_only' else
            'Test' if summary.get('initial_source') == 'saved_version_check' else 'Build')
    document_title = ''
    if files:
        match = re.search(r'<title\b[^>]*>(.*?)</title\s*>', files[-1].read_text(encoding='utf-8'), re.I | re.S)
        if match:
            document_title = html.unescape(re.sub(r'<[^>]*>', '', match.group(1)))
    title = metadata.get('title') or document_title or context.get('original_request') or context.get('purpose') or prompt
    if not title:
        site_title = (summary.get('local_site') or {}).get('title', '')
        title = site_title or ('Imported interface' if mode in ('Run locally', 'Inspect') else 'Website workspace')
    title = ' '.join(str(title).split())[:120 if metadata.get('title') else 84]
    stamp = re.search(r'(\d{8})_(\d{6})(?:_(\d{6}))?', folder.name)
    created = (datetime.strptime(stamp.group(1) + stamp.group(2) + (stamp.group(3) or ''),
                                 '%Y%m%d%H%M%S%f' if stamp.group(3) else '%Y%m%d%H%M%S')
               if stamp else datetime.fromtimestamp(folder.stat().st_mtime))
    return {'folder': folder, 'summary': summary, 'manifest': manifest, 'versions': files,
            'title': title, 'mode': mode, 'created': created, 'status': status}


def list_runs(limit=100):
    found = []
    for folder in artifacts_dir(ARTIFACTS).glob('synthetix_*'):
        if not folder.is_dir() or not (folder / 'summary.json').is_file():
            continue
        try:
            found.append(describe_run(folder))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return sorted(found, key=lambda item: item['created'], reverse=True)[:limit]


def rename_run(folder, title):
    folder = safe_run(folder)
    title = str(title).strip()
    if not 1 <= len(title) <= 120:
        raise ValueError('Use a project name containing 1–120 characters.')
    write_json(folder/'project.json',{'title':title})


def validation_manifest(folder):
    """Never silently weaken an earlier approved test selection."""
    folder=safe_run(folder)
    summary=read_json(folder/'summary.json')
    expected_intent=bool(summary.get('intent_checks_verified') or summary.get('intent_check_steps'))
    expected_counter=bool(summary.get('counter_behavior_verified'))
    for source in versions(folder):
        report=read_json(folder/('report_'+source.stem.split('_')[-1]+'.json'))
        expected_intent=expected_intent or 'intent_check' in report
        expected_counter=expected_counter or 'counter_check' in report
    path=folder/'run.json'
    if not path.is_file():
        if expected_intent:
            raise ValueError('The original approved test steps are missing. Reopen Repair and approve a new selection; runtime-only is not a substitute.')
        if expected_counter:
            return {'counter_checks_selected':True,'intent_checks':[],'recovered_from':'saved_counter_evidence'}
        return {}
    manifest=read_json(path)
    if manifest.get('_read_error'):raise ValueError('The saved test selection could not be read. Reopen Repair to approve fresh checks.')
    from intent_checks import validate_checks
    checks=validate_checks(manifest.get('intent_checks',[]))
    if expected_intent and not checks:raise ValueError('The original approved steps are missing from the saved selection.')
    if expected_counter and manifest.get('counter_checks_selected') is not True:
        raise ValueError('The saved counter-check selection is inconsistent with its report.')
    return manifest


def restore_version(folder, name):
    """Branch a version into an unverified draft; never overwrite prior evidence."""
    original = describe_run(folder)
    document = source_file(folder, name).read_bytes().decode('utf-8')
    draft = artifacts_dir(ARTIFACTS) / ('synthetix_draft_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid.uuid4().hex[:6])
    draft.mkdir(parents=True, exist_ok=False)
    write_text(draft/'version_0.html',document)
    manifest = dict(validation_manifest(folder))
    manifest['restored_from'] = {'folder': str(original['folder']), 'version': name}
    write_json(draft/'run.json',manifest)
    write_json(draft/'project.json',{'title':original['title']+' · restored'})
    summary = {'status': 'restored_unverified', 'output_folder': str(draft), 'repairs_used': 0,
               'initial_source': 'restored_version', 'requested_features_verified': False,
               'restored_from': manifest['restored_from']}
    write_json(draft/'summary.json',summary)
    return draft
