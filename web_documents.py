"""Assemble the self-contained web documents supported by this prototype."""
import re
import html

MAX_CODE_CHARS = 100000


def assemble_document(markup, css='', javascript=''):
    if not all(isinstance(value, str) for value in (markup, css, javascript)):
        raise ValueError('HTML, CSS, and JavaScript must be text.')
    if not any(value.strip() for value in (markup, css, javascript)):
        raise ValueError('Paste some code first.')
    if sum(map(len, (markup, css, javascript))) > MAX_CODE_CHARS:
        raise ValueError('Keep the combined code under 100,000 characters for this prototype.')
    if re.search(r'<html\b', markup, re.I):
        document = markup
    else:
        document = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<title>Synthetix site</title></head><body>' + markup + '</body></html>')
    if css.strip():
        style = '<style>\n' + css + '\n</style>\n'
        if re.search(r'</head\s*>', document, re.I):
            document = re.sub(r'</head\s*>', lambda _: style + '</head>', document, count=1, flags=re.I)
        else:
            document = re.sub(r'<html\b[^>]*>', lambda match: match.group() + '<head>' + style + '</head>',
                              document, count=1, flags=re.I)
    if javascript.strip():
        script = '<script>\n' + javascript + '\n</script>\n'
        if re.search(r'</body\s*>', document, re.I):
            document = re.sub(r'</body\s*>', lambda _: script + '</body>', document, count=1, flags=re.I)
        elif re.search(r'</html\s*>', document, re.I):
            document = re.sub(r'</html\s*>', lambda _: '<body>' + script + '</body></html>',
                              document, count=1, flags=re.I)
        else:
            document += script
    return document


BROWSER_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
               "img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; "
               "object-src 'none'; base-uri 'none'; form-action 'none'")
ISOLATION_CSP = BROWSER_CSP.replace("frame-src 'none'", "frame-src about:")


def restricted_document(document):
    """Install policy before any untrusted token; quoted tags cannot absorb it."""
    meta = '<meta http-equiv="Content-Security-Policy" content="' + BROWSER_CSP + '">'
    return '<!DOCTYPE html>\n' + meta + '\n' + document


def frame_attribute(value):
    # Markdown HTML blocks can terminate at literal blank lines, even in attributes.
    # Character references preserve the source's line endings after HTML parsing.
    return html.escape(value,quote=True).replace('\r','&#13;').replace('\n','&#10;')


def isolated_document(document, title='Synthetix page'):
    """A trusted parent constrains even the untrusted child's own navigations."""
    meta = '<meta http-equiv="Content-Security-Policy" content="' + ISOLATION_CSP + '">'
    frame = ('<iframe sandbox="allow-scripts allow-forms" referrerpolicy="no-referrer" '
             'title="' + html.escape(title, quote=True) + '" srcdoc="' +
             frame_attribute(restricted_document(document)) + '" '
             'style="width:100%;height:100vh;border:0;display:block"></iframe>')
    return ('<!DOCTYPE html><html><head><meta charset="UTF-8">' + meta +
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Synthetix isolated page</title><style>html,body{margin:0;height:100%;overflow:hidden}</style>'
            '</head><body>' + frame + '</body></html>')


def preview_frame_html(document, title):
    return ('<div class="preview-shell"><iframe sandbox="allow-scripts allow-forms" '
            'referrerpolicy="no-referrer" title="Preview isolation boundary" srcdoc="' +
            frame_attribute(isolated_document(document, title)) + '" '
            'style="width:100%;height:560px;border:0;display:block"></iframe></div>')
