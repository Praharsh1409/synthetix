"""Pure verdicts: incomplete evidence and execution failures never imply a pass."""
from browser_safety import ERROR_KINDS


def report_problem(report):
    if not isinstance(report,dict):return 'The saved report is not an object.'
    if report.get('_read_error'):return report['_read_error']
    errors=report.get('combined_errors',report)
    if not isinstance(errors,dict):return 'The saved report has invalid error data.'
    if not all(isinstance(errors.get(kind),list) for kind in ('javascript_errors','console_errors')):
        return 'The saved report is incomplete. Run checks to create fresh evidence.'
    if any(not isinstance(errors.get(kind,[]),list) for kind in ERROR_KINDS):
        return 'The saved error data is invalid.'
    for key in ('counter_check','intent_check'):
        test=report.get(key)
        if test is None:continue
        if not isinstance(test,dict):return 'The saved test result is invalid.'
        if not test.get('skipped') and test.get('passed') not in (True,False):
            return 'A selected test has no completed result.'
        if test.get('passed') is False and not test.get('skipped') and not any(test.get(kind) for kind in ERROR_KINDS):
            return 'A selected test did not establish a result.'
    return None


def version_verdict(report):
    if not report:return 'Not tested','warning'
    if report_problem(report):return 'Report unavailable','warning'
    errors=report.get('combined_errors',report)
    if errors.get('execution_errors'):return 'Could not run','warning'
    if any(errors.get(kind) for kind in ERROR_KINDS):return 'Checks failed','error'
    tests=[report[key] for key in ('counter_check','intent_check') if isinstance(report.get(key),dict)]
    if any(test.get('skipped') for test in tests):return 'Tests could not run','warning'
    if tests and all(test.get('passed') is True for test in tests):return 'Selected checks passed','success'
    if report.get('passed') is False or report.get('status')=='error':return 'Incomplete result','warning'
    return 'Runtime checks passed','success'
