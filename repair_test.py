import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import expect
from browser_safety import empty_report,isolated_page,load_document,ERROR_KINDS
from generate_ui import completion_content

from browser_check import check_html


PROJECT_FOLDER = Path(__file__).parent
load_dotenv(PROJECT_FOLDER / ".env")

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

BROKEN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Synthetix repair test</title>
</head>
<body>
    <h1>Synthetix</h1>

    <button id="demo" onclick="showMessage()">Test button</button>
    <p id="status">Waiting</p>

    <script>
        showMessage();
    </script>
</body>
</html>
"""


def request_repair(html_code, errors):
    api_key = os.getenv("NEBIUS_API_KEY")

    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is missing from .env.")

    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=api_key,
        timeout=90.0,
        max_retries=0,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Repair the supplied HTML and JavaScript. "
                    "Return only the complete HTML document. "
                    "Do not include explanations or Markdown fences. "
                    "Preserve the heading, button, status paragraph, "
                    "their IDs, and the initial showMessage() call. "
                    "Define showMessage() so that it sets the status "
                    "paragraph text to exactly: Button works! "
                    "The button must also call this function when clicked. "
                    "Use no external scripts, libraries, or network requests."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Broken HTML:\n{html_code}\n\n"
                    f"Observed browser errors:\n{json.dumps(errors)}"
                ),
            },
        ],
        max_tokens=4096,
    )

    repaired_html=completion_content(response)

    # Remove a surrounding Markdown code fence if the model adds one.
    if repaired_html.startswith("```"):
        lines = repaired_html.splitlines()

        if lines[-1].strip() != "```":
            raise RuntimeError("The model returned an incomplete code block.")

        repaired_html = "\n".join(lines[1:-1]).strip()

    if not repaired_html.lower().startswith(("<!doctype html", "<html")):
        raise RuntimeError("The model did not return a complete HTML document.")

    return repaired_html


def check_button_behavior(html_code):
    report=empty_report()
    with isolated_page(report) as page:
        load_document(page,html_code)
        expect(page.locator('#status')).to_be_visible(timeout=5000)
        expect(page.locator('#status')).to_have_text('Button works!',timeout=5000)
        page.locator('#status').evaluate("element => element.textContent='Waiting'")
        page.locator('#demo').click()
        expect(page.locator('#status')).to_have_text('Button works!',timeout=5000)
        page.wait_for_timeout(500)
    if any(report.get(kind) for kind in ERROR_KINDS):
        raise AssertionError('The button check observed browser errors: '+json.dumps(report))


def main():
    print("1. Checking the deliberately broken page...")

    before = check_html(BROKEN_HTML, "before_repair.png")

    errors = {
        "javascript_errors": before["javascript_errors"],
        "console_errors": before["console_errors"],
        "execution_errors":before.get("execution_errors",[]),
    }

    print(json.dumps(errors, indent=2))
    if errors.get("execution_errors"):
        print("Browser execution could not complete; no model repair was requested.")
        return 1

    if not any(errors.values()):
        raise RuntimeError("Expected a browser error, but none was detected.")

    print("\n2. Asking Nemotron to repair the page...")

    repaired_html = request_repair(BROKEN_HTML, errors)

    output_folder = PROJECT_FOLDER / "artifacts"
    output_folder.mkdir(exist_ok=True)

    repaired_file = output_folder / "repaired.html"
    repaired_file.write_text(repaired_html, encoding="utf-8")

    print(f"Saved repaired HTML: {repaired_file}")

    print("\n3. Checking the repaired page...")

    after = check_html(repaired_html, "after_repair.png")
    print(json.dumps(after, indent=2))

    if any(after.get(kind) for kind in ERROR_KINDS):
        print("\nREPAIR FAILED: Browser errors remain.")
        return 1

    print("\n4. Checking that the button actually works...")

    check_button_behavior(repaired_html)

    print("\nPASS: No browser errors were observed.")
    print("PASS: The initial message and button-click checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())