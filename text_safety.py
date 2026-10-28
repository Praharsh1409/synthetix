"""Render untrusted titles, model prose and diagnostics as literal Markdown text."""
import re


def markdown_text(value):
    # Escaping punctuation prevents images/links from becoming active root-page UI.
    return re.sub(r'([\\`*_{}\[\]()#+\-.!|<>:])',r'\\\1',str(value))
