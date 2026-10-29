"""Publish static sites and return a URL only after an HTTP check succeeds."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from urllib.request import Request, urlopen
from artifact_io import write_text, write_json
from web_documents import isolated_document
from runtime_paths import cloud_mode

ROOT = Path(__file__).resolve().parent
SITES = ROOT / 'artifacts' / 'local_sites'
STATE = ROOT / 'artifacts' / 'local_host' / 'server.json'
_spawned_processes = {}


def running_host():
    if cloud_mode():
        return None
    try:
        record = json.loads(STATE.read_text(encoding='utf-8'))
        port = record['port']
        if not isinstance(port, int) or not 1 <= port <= 65535:
            return None
        request=Request(f'http://127.0.0.1:{port}/_synthetix_health',headers={'X-Synthetix-Token':record['token']})
        with urlopen(request,timeout=1) as response:
            health = json.load(response)
        if health.get('service') == 'synthetix-static-host' and (health.get('protocol')==2 or health.get('token')==record.get('token')):
            return record
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


@contextmanager
def startup_lock():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    lock = STATE.parent / 'startup.lock'
    deadline = time.monotonic() + 15
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError('Local hosting is busy starting. Try again shortly.')
            time.sleep(0.1)
    try:
        yield
    finally:
        lock.rmdir()


def ensure_host():
    record = running_host()
    if record:
        return record
    with startup_lock():
        record = running_host()
        if record:
            return record
        SITES.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment['PYTHONUTF8'] = '1'
        environment.pop('NEBIUS_API_KEY', None)
        with (STATE.parent / 'server.log').open('ab') as log:
            process = subprocess.Popen(
                [sys.executable, '-u', str(ROOT / 'local_host.py'), '--sites', str(SITES), '--state', str(STATE)],
                cwd=str(ROOT), env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            record = running_host()
            if record:
                _spawned_processes[record['port']]=process
                return record
            if process.poll() is not None:
                raise RuntimeError('Local site host could not start. Check artifacts/local_host/server.log.')
            time.sleep(0.15)
        process.terminate()
        raise RuntimeError('The local site host did not become ready within ten seconds.')


def publish_html(document, title='Synthetix site', source='submitted_html', site_id=None):
    if not isinstance(document, str) or not document.strip():
        raise ValueError('There is no HTML to host.')
    if cloud_mode():
        return {'mode': 'browser_preview', 'title': str(title)[:120], 'source': source,
                'http_verified': False, 'note': 'Available in the browser preview. Download HTML to run it on your computer.'}
    site_id = site_id or uuid.uuid4().hex
    if not re.fullmatch(r'[a-f0-9]{32}', site_id):
        raise ValueError('Invalid local site ID.')
    folder = SITES / site_id
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise ValueError('Site directories cannot be symlinks.')
    target = folder / 'index.html'
    if target.is_symlink():
        raise ValueError('Site documents cannot be symlinks.')
    write_text(target,document)
    display_title=str(title)[:120]
    write_json(folder/'site.json',{'title':display_title,'site_id':site_id,'http_verified':False})
    record = ensure_host()
    url = f'http://127.0.0.1:{record["port"]}/sites/{site_id}/'
    with urlopen(url, timeout=3) as response:
        if response.status != 200 or response.read().decode('utf-8') != isolated_document(document,display_title):
            raise RuntimeError('The hosted document did not pass its HTTP check.')
    site = {'site_id': site_id, 'title': str(title)[:120], 'source': source, 'url': url,
            'http_verified': True, 'published_at': datetime.now(timezone.utc).isoformat()}
    write_json(folder/'site.json',site)
    return site


def stop_host():
    record = running_host()
    if not record:
        return False
    request = Request(f'http://127.0.0.1:{record["port"]}/_synthetix_stop', method='POST',
                      headers={'X-Synthetix-Token': record['token']}, data=b'')
    with urlopen(request, timeout=3) as response:
        accepted = response.status == 200
    if accepted:
        deadline = time.monotonic() + 3
        while running_host() and time.monotonic() < deadline:
            time.sleep(0.1)
    stopped=running_host() is None
    if stopped:
        process=_spawned_processes.pop(record['port'],None)
        if process is not None:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
    return accepted and stopped
