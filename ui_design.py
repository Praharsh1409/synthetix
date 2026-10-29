"""Authored Synthetix presentation; submitted HTML never executes here."""
import base64
import html
import json
from pathlib import Path
from runtime_paths import artifacts_dir

import streamlit as st

ROOT = Path(__file__).resolve().parent


@st.cache_data
def presentation_styles(style_version):
    fonts = []
    for weight in [400, 500, 700]:
        data = base64.b64encode((ROOT / 'assets' / f'general-sans-{weight}.woff2').read_bytes()).decode('ascii')
        fonts.append(f"@font-face {{font-family:'General Sans';src:url(data:font/woff2;base64,{data}) format('woff2');font-style:normal;font-weight:{weight};font-display:swap;}}")
    return '<style>' + ''.join(fonts) + (ROOT / 'site.css').read_text(encoding='utf-8') + '</style>'


def apply_design():
    st.html(presentation_styles((ROOT / 'site.css').stat().st_mtime_ns))


def render_home(pages):
    document = (ROOT / 'home.html').read_text(encoding='utf-8')
    # Show a genuine saved report; never invent successful run statistics.
    folder = artifacts_dir(ROOT / 'artifacts') / 'synthetix_20261024_200009_615019'
    try:
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        report = json.loads((folder / 'report_1.json').read_text(encoding='utf-8'))
        checks = report['intent_check']['checks_passed']
        repairs, count = str(summary['repairs_used']), str(len(checks))
        items = ''.join('<li>' + html.escape(check) + '</li>' for check in checks)
        source = 'Saved run from 24 October 2026. Supplied demo code; passing result after one AI repair. This is a saved report, not a live benchmark.'
    except (OSError, ValueError, KeyError):
        repairs = count = '—'
        items = '<li>A completed repair will have its selected checks listed in the workspace.</li>'
        source = 'No saved example is available in this checkout. Run the controlled demo to create a report.'
    for key, value in {'__REPAIRS__':repairs, '__CHECK_COUNT__':count,
                       '__CHECK_ITEMS__':items, '__REPORT_SOURCE__':html.escape(source)}.items():
        document = document.replace(key, value)
    # Authored HTML only. Uploaded/generated pages remain in the preview sandbox.
    st.html(document)


def install_scroll_motion():
    st.html((ROOT / 'scroll_motion.html').read_text(encoding='utf-8'), unsafe_allow_javascript=True)
