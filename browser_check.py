import json
from pathlib import Path
from runtime_paths import artifacts_dir

from browser_safety import empty_report, isolated_page, load_document, finish_report, execution_error


ARTIFACTS=Path(__file__).parent/'artifacts'


def check_html(html_code, screenshot_name):
    output_folder=artifacts_dir(ARTIFACTS).resolve()
    screenshot_path=(output_folder/screenshot_name).resolve()
    screenshot_path.relative_to(output_folder)
    screenshot_path.parent.mkdir(parents=True,exist_ok=True)
    report=empty_report()
    try:
        with isolated_page(report) as page:
            load_document(page,html_code)
            page.wait_for_timeout(500)
            # Bound raster allocation: untrusted CSS cannot request a huge full-page image.
            page.screenshot(path=str(screenshot_path),full_page=False,timeout=5000)
            report['screenshot']=str(screenshot_path)
    except Exception as error:
        execution_error(report,error)
    return finish_report(report)


if __name__ == "__main__":
    working_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Working example</title>
        </head>
        <body>
            <h1>Synthetix browser test</h1>
            <p>This page has no intentional JavaScript errors.</p>
        </body>
    </html>
    """

    broken_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Broken example</title>
        </head>
        <body>
            <h1>This page contains a JavaScript bug</h1>

            <script>
                console.error("Example console error");
                missingFunction();
            </script>
        </body>
    </html>
    """

    print("\n--- WORKING PAGE ---")
    working_result = check_html(working_html, "working.png")
    print(json.dumps(working_result, indent=2))

    print("\n--- BROKEN PAGE ---")
    broken_result = check_html(broken_html, "broken.png")
    print(json.dumps(broken_result, indent=2))