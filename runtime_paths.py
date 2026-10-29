"""Thread-scoped visitor workspaces; workers inherit only their own workspace ID."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import re
import threading

ROOT = Path(__file__).resolve().parent
_session = ContextVar('synthetix_session', default=None)
_slots = threading.BoundedSemaphore(1)


def session_id():
    value = _session.get() or os.getenv('SYNTHETIX_CLOUD_SESSION')
    if value is not None and not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Invalid visitor workspace.')
    return value


def cloud_mode():
    return session_id() is not None


@contextmanager
def visitor_workspace(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{64}', identifier):
        raise ValueError('Invalid visitor workspace.')
    token = _session.set(identifier)
    try:
        yield
    finally:
        _session.reset(token)


def artifacts_dir(default=None):
    identifier = session_id()
    if not identifier:
        return Path(default) if default is not None else ROOT / 'artifacts'
    base = ROOT / 'artifacts' / 'visitors'
    folder = base / identifier
    if base.is_symlink() or folder.is_symlink():
        raise ValueError('Visitor workspaces cannot be links.')
    return folder


def interview_dir(default):
    return artifacts_dir() / 'design_interviews' if cloud_mode() else Path(default)


def worker_environment(original, api_key=''):
    result = dict(original)
    result.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    if cloud_mode():
        result['SYNTHETIX_CLOUD_SESSION'] = session_id()
        # Never fall back to the owner's credentials in a public visitor session.
        result.pop('NEBIUS_API_KEY', None)
        if api_key.strip():
            result['NEBIUS_API_KEY'] = api_key.strip()
    return result


def requires_model(job):
    return job.get('workflow') not in ('diagnose', 'test_saved', 'host_code', 'host_existing')


@contextmanager
def job_slot():
    if not cloud_mode():
        yield
        return
    if not _slots.acquire(blocking=False):
        raise ValueError('Another visitor is using the browser or AI worker. Your work is saved; try again shortly.')
    try:
        root = artifacts_dir()
        if root.exists() and sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) > 25_000_000:
            raise ValueError('This temporary workspace has reached its storage limit. Download your HTML and start a new browser session.')
        yield
    finally:
        _slots.release()
