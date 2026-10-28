"""A small declarative browser-test language; never executes model-written Python."""
from playwright.sync_api import expect
from browser_safety import empty_report, isolated_page, load_document, finish_report, execution_error

ACTIONS = {'click', 'fill', 'expect_text', 'expect_value', 'expect_visible'}
LOCATORS = {'role', 'css', 'text', 'label'}


def validate_checks(checks):
    if not isinstance(checks, list) or len(checks) > 20:
        raise ValueError('Checks must be a JSON list containing at most 20 steps.')
    for index, item in enumerate(checks, 1):
        if not isinstance(item, dict) or item.get('action') not in ACTIONS:
            raise ValueError(f'Check {index}: unsupported action.')
        if item.get('by') not in LOCATORS:
            raise ValueError(f'Check {index}: choose a role, css, text, or label locator.')
        allowed = {'action', 'by', 'name', 'role', 'selector', 'text', 'value', 'description'}
        if set(item) - allowed:
            raise ValueError(f'Check {index}: unsupported fields.')
        if any(not isinstance(value, str) or len(value) > 2000 for value in item.values()):
            raise ValueError(f'Check {index}: field values must be short text strings.')
        required = {'role': ('role', 'name'), 'css': ('selector',), 'text': ('name',), 'label': ('name',)}[item['by']]
        for key in required:
            if not item.get(key, '').strip():
                raise ValueError(f'Check {index}: missing {key}.')
        if item['action'] == 'expect_text' and 'text' not in item:
            raise ValueError(f'Check {index}: missing expected text.')
        if item['action'] in ('fill', 'expect_value') and 'value' not in item:
            raise ValueError(f'Check {index}: missing value.')
    if checks and not any(item['action'].startswith('expect_') for item in checks):
        raise ValueError('Include at least one user-visible assertion, or use [] for runtime-only checking.')
    return checks


def describe_check(check):
    target = check.get('selector') or check.get('name')
    action = check['action'].replace('_', ' ')
    expected = check.get('text', check.get('value'))
    return check.get('description') or f'{action}: {target}' + (f' → {expected}' if expected is not None else '')


def check_intent(document, checks):
    validate_checks(checks)
    report=empty_report()
    planned=[describe_check(check) for check in checks]
    report['checks_not_run']=list(planned)
    step='Load page'
    try:
        with isolated_page(report) as page:
            try:
                load_document(page, document)
            except Exception as error:
                execution_error(report,error)
            else:
                for index,check in enumerate(checks):
                    step=describe_check(check)
                    report['checks_not_run']=planned[index+1:]
                    try:
                        by=check['by']
                        if by=='role': locator=page.get_by_role(check['role'],name=check['name'],exact=True)
                        elif by=='css': locator=page.locator('css='+check['selector'])
                        elif by=='text': locator=page.get_by_text(check['name'],exact=True)
                        else: locator=page.get_by_label(check['name'],exact=True)
                        action=check['action']
                        if action=='click': locator.click()
                        elif action=='fill': locator.fill(check['value'])
                        else:
                            expect(locator).to_be_visible(timeout=5000)
                            if action=='expect_text': expect(locator).to_have_text(check['text'],timeout=5000)
                            elif action=='expect_value': expect(locator).to_have_value(check['value'],timeout=5000)
                        report['checks_passed'].append(step)
                    except Exception as error:
                        report['behavior_errors'].append({'step':step,'details':str(error)[:4000]})
                        break
                # Match the runtime observation window, including async click handlers.
                page.wait_for_timeout(500)
    except Exception as error:
        execution_error(report,error)
    return finish_report(report)
