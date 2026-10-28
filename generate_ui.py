import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from browser_check import check_html


PROJECT_FOLDER = Path(__file__).parent
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

load_dotenv(PROJECT_FOLDER / ".env")


def completion_content(response):
    choices=getattr(response,'choices',None)
    if not isinstance(choices,(list,tuple)) or not choices:
        raise RuntimeError('The model returned no completion choices.')
    choice=choices[0]
    reason=getattr(choice,'finish_reason',None)
    if reason=='length':
        raise RuntimeError('The model reached the token limit. Incomplete output will not be used.')
    if reason!='stop':
        raise RuntimeError('The model did not finish a normal text response. Retry the request.')
    message=getattr(choice,'message',None)
    text=getattr(message,'content',None)
    if getattr(message,'refusal',None) or not isinstance(text,str) or not text.strip():
        raise RuntimeError('The model returned no usable text content.')
    return text.strip()


def generate_html(user_prompt):
    api_key = os.getenv("NEBIUS_API_KEY")

    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is missing from .env.")

    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=api_key,
        timeout=120.0,
        max_retries=2,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate small, self-contained web interfaces. "
                    "Return only one complete HTML document, starting "
                    "with <!DOCTYPE html> and ending with </html>. "
                    "Put all CSS inside a style element and all "
                    "JavaScript inside script elements. "
                    "Use plain HTML, CSS, and JavaScript only. "
                    "Do not use Markdown fences or explanations. "
                    "Do not load external libraries, fonts, images, "
                    "stylesheets, scripts, or other URLs. "
                    "Do not make network requests. "
                    "Use CSS shapes or text when illustrations are needed. "
                    "Implement the user's requested features. "
                    "Follow the approved brief's subject-specific visual direction. "
                    "Use coherent spacing, readable typography, useful navigation, "
                    "keyboard-visible focus, and clear interaction states. "
                    "Avoid a stock gradient hero or repeated card grid unless the brief requests it. "
                    "Do not invent customer logos, testimonials, numerical business claims, "
                    "or functioning backend integrations. "
                    "Keep the page responsive and the code concise."
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        max_tokens=8192,
    )

    html_code=completion_content(response)

    # Handle a surrounding Markdown fence if one is returned.
    if html_code.startswith("```"):
        lines = html_code.splitlines()

        if lines[-1].strip() != "```":
            raise RuntimeError("The model returned an incomplete code block.")

        html_code = "\n".join(lines[1:-1]).strip()

    if not html_code.lower().startswith("<!doctype html"):
        raise RuntimeError("The response did not start with <!DOCTYPE html>.")

    if not html_code.lower().endswith("</html>"):
        raise RuntimeError("The response did not end with </html>.")

    return html_code


def main():
    print("SYΝTHETIX — UI generation test")

    user_prompt = input("\nDescribe the interface you want:\n> ").strip()

    if not user_prompt:
        print("No prompt entered. Please run the script again.")
        return

    if len(user_prompt) > 4000:
        print("Please keep this first prompt under 4,000 characters.")
        return

    print("\n1. Asking Nemotron to generate HTML...")

    html_code = generate_html(user_prompt)

    run_id = "generation_" + datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_folder = PROJECT_FOLDER / "artifacts" / run_id
    output_folder.mkdir(parents=True, exist_ok=True)

    html_path = output_folder / "generated.html"
    html_path.write_text(html_code, encoding="utf-8")

    prompt_path = output_folder / "prompt.txt"
    prompt_path.write_text(user_prompt, encoding="utf-8")

    print(f"Saved HTML: {html_path}")

    print("\n2. Checking the generated page in Chromium...")

    result = check_html(
        html_code,
        f"{run_id}/preview.png",
    )

    report_path = output_folder / "browser_report.json"
    report_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2))

    if result.get("execution_errors"):
        print("Browser execution could not complete. No runtime pass is claimed.")
        return 1
    if result["javascript_errors"] or result["console_errors"]:
        print("\nBrowser errors were detected.")
        print("The code and report are saved for inspection.")
    else:
        print("\nNo runtime errors were observed during this check.")
        print("The requested features have not been verified yet.")

    print(f"\nOpen this folder in VS Code: {output_folder}")
    return 1 if result["javascript_errors"] or result["console_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())