import json
import sys
from datetime import datetime
from pathlib import Path

from browser_check import check_html
from artifact_io import public_error
from browser_safety import ERROR_KINDS
from repair_test import (
    BROKEN_HTML,
    request_repair,
    check_button_behavior,
)


MAX_REPAIRS = 3


def main():
    current_html = BROKEN_HTML

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    output_folder = Path(__file__).parent / "artifacts" / run_id
    output_folder.mkdir(parents=True, exist_ok=True)

    # Check the original page, then check after each repair.
    for repair_count in range(MAX_REPAIRS + 1):
        print(f"\n--- Checking version {repair_count} ---")

        html_path = output_folder / f"version_{repair_count}.html"
        html_path.write_text(current_html, encoding="utf-8")

        result = check_html(
            current_html,
            f"{run_id}_version_{repair_count}.png",
        )

        errors = {
            "javascript_errors": result["javascript_errors"],
            "console_errors": result["console_errors"],
            "behavior_errors": [],
            "execution_errors":result.get("execution_errors",[]),
        }

        # If the page loads without errors, test the button.
        if not any(errors.values()):
            try:
                check_button_behavior(current_html)
            except Exception as error:
                errors["behavior_errors"].append(str(error))

        # Save the evidence for this version.
        report_path = output_folder / f"report_{repair_count}.json"
        report_path.write_text(
            json.dumps(errors, indent=2),
            encoding="utf-8",
        )

        if errors["execution_errors"]:
            print("STOPPED: Browser execution could not complete.")
            print(json.dumps(errors,indent=2))
            return 1
        if not any(errors.values()):
            print("\nSUCCESS: The browser and button checks passed.")
            print(f"Repairs used: {repair_count}")
            print(f"Checked HTML: {html_path}")
            print(f"Evidence folder: {output_folder}")
            return 0

        print("Problems detected:")
        print(json.dumps(errors, indent=2))

        if repair_count == MAX_REPAIRS:
            print("\nSTOPPED: The repair limit was reached.")
            print("The latest version still fails the checks.")
            print(f"Evidence folder: {output_folder}")
            return 1

        print(f"\nRequesting repair {repair_count + 1}/{MAX_REPAIRS}...")

        try:
            current_html = request_repair(current_html, errors)
        except Exception as error:
            print(f"\nSTOPPED: The repair request failed: {public_error(error)}")
            print(f"Evidence folder: {output_folder}")
            return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())