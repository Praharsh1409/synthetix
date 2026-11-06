# Synthetix

**Your independent frontend workbench.**

Synthetix helps you import, preview, test and review self-contained HTML, CSS and JavaScript websites. Run real Chromium checks, inspect their evidence, edit your code and export the result.

[Open the workspace](https://praharsh1409.github.io/synthetix/app.html) · [Project website](https://praharsh1409.github.io/synthetix/) · [Local setup](#local-setup)

## Current availability

No AI provider is enabled in this development release. AI conversations, design refinement, website generation and automatic repair are temporarily unavailable while a replacement backend is developed and verified. The experimental local model has not met the repair-quality criteria and is not connected to the public app.

The app does not ask for an API key, load provider credentials from `.env`, or fall back to an owner's key. No inference SDK or provider endpoint is configured. A disabled action explains why it is unavailable; example projects and scripted walkthroughs are labelled and never presented as generated results.

## What works now

- **Import and preview:** paste HTML with optional CSS/JavaScript and run the original page in an isolated preview. Previewing does not change the source.
- **Inspect:** collect JavaScript exceptions and console errors through sandboxed, offline Chromium.
- **Approve browser checks:** write declarative steps, review their descriptions, explicitly approve them and run them without AI edits. Supported actions are `click`, `fill`, `expect_text`, `expect_value` and `expect_visible`; executable model-written test code is not accepted.
- **Review:** inspect code, screenshots, reports, versions and differences. Restore a version into an untested draft. Recheck saved versions against their recorded assertions.
- **Edit and export:** inspect a manually edited draft as a new run and download the selected HTML.
- **Run locally:** the local entry point can start a loopback-only server. Online sessions use the isolated preview instead of an unusable visitor-localhost link.
- **Explore:** interactive prebuilt examples and the scroll walkthrough remain available without a model call.

Existing planning, editable-brief approval, behavior-test approval and bounded repair logic remain in the source for the future backend. Automatic repairs retain a maximum of three attempts and rerun the same checks. Unavailable AI actions do not fabricate results or mark a project as generated.

## Check an interaction

After importing a page on **Test and repair**, choose **Find errors**. Open **Write and approve your own browser checks**, edit the JSON, review the listed steps, select **I approve these browser checks**, then choose **Run approved checks**. For example, a counter with a button labelled Add and an output with ID `value` can use:

```json
[
  {"action":"click","by":"role","role":"button","name":"Add"},
  {"action":"expect_text","by":"css","selector":"#value","text":"1"}
]
```

This example is not a test for every website. Match selectors, actions and expected outcomes to your page. Changing the source requires another inspection; changing checks requires fresh approval. An empty list checks runtime errors only. Passing selected checks does not establish all behavior, visual quality, accessibility or every device.

## Use online

[GitHub Pages](https://praharsh1409.github.io/synthetix/) provides the public website and embeds the [Streamlit workspace](https://synthetix-workspace.streamlit.app/). Each visitor receives a separate temporary workspace. Download your HTML before closing or refreshing: hosting may restart, sleep or discard temporary work. No accounts or permanent project storage are provided.

The deployment uses repository `Praharsh1409/synthetix`, branch `main`, entry point `cloud_app.py` and Python 3.12. No model-service secrets are required. `packages.txt` supplies Debian Chromium and its sandbox helper; failure to run the sandbox is an execution error, not a reason to disable it.

## Local setup

Python 3.12 is the verified local runtime. On Windows:

```powershell
git clone https://github.com/Praharsh1409/synthetix.git
cd synthetix
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **http://127.0.0.1:8501/** after the server starts. No `.env` or API credentials are needed. The default listener is restricted to this computer. Saved local work is stored in `artifacts/`, which is excluded from the repository.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

The suite includes real browser checks, source preservation, saved reports, isolation, approval gates, unavailable-backend handling and controlled response-validation fixtures. Mocked AI tests do not establish live model performance. Test results belong to the particular source revision and environment where they ran.

## Architecture

| Component | Responsibility |
|---|---|
| `app.py`, `cloud_app.py`, `workspace_ui.py` | Navigation, local/cloud entry points and review workspace |
| `ai_backend.py` | Explicit unavailable-provider boundary; no credentials or network calls |
| `ai_tasks.py`, `generate_ui.py`, `synthetix.py` | Planning/generation/repair contracts retained for a future backend |
| `design_interview.py`, `guided_interview.py` | Persistent requirements, style selection and brief approval |
| `ui_worker.py` | Isolated worker operations and manual approved browser checks |
| `browser_safety.py`, `intent_checks.py` | Offline sandboxed Chromium and declarative assertions |
| `project_store.py`, `artifact_io.py`, `reporting.py` | Versions, atomic checkpoints, differences and honest outcomes |
| `credential_safety.py`, `runtime_paths.py` | Credential-filtered process environments and visitor scope |
| `hosting.py`, `local_host.py`, `web_documents.py` | Loopback hosting and isolated previews |

## Scope and safety

The product focuses on self-contained frontend HTML/CSS/JavaScript. It does not implement website payments, authentication, databases or email services. Uploaded pages are untrusted: previews use sandboxed frames and content policies; browser checks block network access. Credentials are filtered from browser, worker and local-host processes.

The hosted service has bounded jobs, timeouts, diagnostics and temporary storage, with one worker admitted at a time. These controls are not full process-container or resource isolation. Do not upload secrets or sensitive source. A failed check or unavailable service must not be labelled a success.

## Website and license

GitHub Pages serves `main` → `/docs`; Streamlit runs Python and Chromium. Website assets use relative paths. The graphite/electric-blue workbench, prebuilt examples and motion respect reduced-motion preferences and preserve each preview's own colors.

Synthetix source is available under the [MIT License](LICENSE). See [asset sources and font licenses](assets/studio/SOURCES.txt) for third-party materials; their licenses remain in force.
