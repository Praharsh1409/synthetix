import json
import re
import sys
from pathlib import Path

from playwright.sync_api import expect
from browser_safety import empty_report, isolated_page, load_document, finish_report, execution_error


COUNTER_STEPS = ['Exactly one counter display exists','Initial number is 0',
                 'Increase changes 0 to 1','Increase changes 1 to 2',
                 'Decrease changes 2 to 1','Reset changes 1 to 0']


def check_counter(html_code):
    report=empty_report()
    report['checks_not_run']=list(COUNTER_STEPS)
    try:
        with isolated_page(report) as page:
            try: load_document(page,html_code)
            except Exception as error: execution_error(report,error)
            else:
                counter=page.get_by_text(re.compile(r'^-?\d+$')).filter(visible=True)
                for index,step in enumerate(COUNTER_STEPS):
                    report['checks_not_run']=COUNTER_STEPS[index+1:]
                    try:
                        if index==0: expect(counter).to_have_count(1,timeout=5000)
                        else:
                            if index>=2:
                                button={2:'Increase',3:'Increase',4:'Decrease',5:'Reset'}[index]
                                page.get_by_role('button',name=button,exact=True).click()
                            expect(counter).to_be_visible(timeout=5000)
                            expect(counter).to_have_text({1:'0',2:'1',3:'2',4:'1',5:'0'}[index],timeout=5000)
                        report['checks_passed'].append(step)
                    except Exception as error:
                        report['behavior_errors'].append({'step':step,'details':str(error)[:4000]})
                        break
                page.wait_for_timeout(500)
    except Exception as error: execution_error(report,error)
    return finish_report(report)


def main():
    project_folder = Path(__file__).parent

    # You may supply a specific HTML path after the script name.
    if len(sys.argv) > 1:
        html_path = Path(sys.argv[1])
    else:
        candidates = list(
            (project_folder / "artifacts").glob("synthetix_*/final.html")
        )

        if not candidates:
            print("No final.html found in the Synthetix run folders.")
            return 1

        html_path = max(
            candidates,
            key=lambda path: path.stat().st_mtime,
        )

    print(f"\nTesting: {html_path}")

    html_code = html_path.read_text(encoding="utf-8")
    report = check_counter(html_code)

    report_path = html_path.parent / "counter_report.json"
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    for check in report["checks_passed"]:
        print(f"PASS: {check}")

    if report["passed"]:
        print("\nCOUNTER CHECKS PASSED")
    else:
        print("\nCOUNTER CHECKS FAILED")
        print(json.dumps(report, indent=2))

    print(f"\nReport saved: {report_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())