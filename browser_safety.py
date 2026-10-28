"""Shared bounded, offline Chromium contexts for untrusted documents."""
from contextlib import contextmanager
import os

from playwright.sync_api import sync_playwright
from web_documents import restricted_document

ERROR_KINDS=('javascript_errors','console_errors','behavior_errors','execution_errors')
MAX_ERROR_MESSAGES=50


def record_error(messages, value):
    if len(messages)<MAX_ERROR_MESSAGES:
        messages.append(str(value)[:2000])
    elif len(messages)==MAX_ERROR_MESSAGES:
        messages.append('Additional error messages omitted after the diagnostic limit.')


def empty_report():
    return {**{kind:[] for kind in ERROR_KINDS},'checks_passed':[],'checks_not_run':[],
            'limits':{'load_timeout_ms':10000,'assertion_timeout_ms':5000,'observation_ms':500,
                      'max_error_messages':MAX_ERROR_MESSAGES,'screenshot_viewport':[1280,720],'js_old_space_mb':128}}


def finish_report(report):
    report['passed']=not any(report.get(kind) for kind in ERROR_KINDS)
    report['status']='error' if report.get('execution_errors') else ('passed' if report['passed'] else 'failed')
    return report


def browser_environment():
    # Renderer processes have no need for application/cloud credentials.
    allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE',
             'LOCALAPPDATA','APPDATA','PROGRAMFILES','PROGRAMFILES(X86)',
             'HOMEDRIVE','HOMEPATH','HOME','DISPLAY','XAUTHORITY','LANG',
             'PLAYWRIGHT_BROWSERS_PATH'}
    return {key:value for key,value in os.environ.items() if key.upper() in allowed}


@contextmanager
def isolated_page(report):
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,chromium_sandbox=True,
                                             timeout=10000,env=browser_environment(),
                                             args=['--js-flags=--max-old-space-size=128'])
        try:
            context=browser.new_context(offline=True,service_workers='block',
                                       viewport={'width':1280,'height':720},accept_downloads=False)
            context.route('**/*',lambda route:route.abort('blockedbyclient'))
            context.route_web_socket('**/*',lambda socket:socket.close())
            page=context.new_page()
            page.set_default_timeout(5000)
            page.on('pageerror',lambda error:record_error(report['javascript_errors'],error))
            page.on('console',lambda message:record_error(report['console_errors'],message.text)
                    if message.type=='error' else None)
            yield page
        finally:
            browser.close()


def load_document(page, document):
    if not isinstance(document,str) or len(document)>100000:
        raise ValueError('Browser input must be HTML text under 100,000 characters.')
    page.set_content(restricted_document(document),wait_until='load',timeout=10000)


def execution_error(report, error):
    record_error(report['execution_errors'],type(error).__name__+': '+str(error))
