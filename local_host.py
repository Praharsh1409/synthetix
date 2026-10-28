"""A localhost-only static host serving published site documents, never the project root."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
from web_documents import ISOLATION_CSP, isolated_document

SITE_ID = re.compile(r'^[a-f0-9]{32}$')
CSP = ISOLATION_CSP + "; sandbox allow-scripts allow-forms"


def make_handler(sites, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', CSP)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def valid_host(self):
            expected={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Host','').lower() in expected:return True
            self.send_body(403,b'Unrecognized host.','text/plain; charset=utf-8')
            return False

        def authorized(self):
            return secrets.compare_digest(self.headers.get('X-Synthetix-Token','').encode('utf-8'),token.encode('ascii'))

        def do_GET(self):
            if not self.valid_host():return
            path = urlsplit(self.path).path
            if path == '/_synthetix_health':
                if not self.authorized():
                    self.send_body(403,b'Forbidden.','text/plain; charset=utf-8')
                    return
                self.send_body(200,json.dumps({'service':'synthetix-static-host','protocol':2}).encode(),
                               'application/json; charset=utf-8')
                return
            parts = path.strip('/').split('/')
            if len(parts) == 2 and parts[0] == 'sites' and SITE_ID.fullmatch(parts[1]):
                site_folder = sites / parts[1]
                file = site_folder / 'index.html'
                try:
                    file.resolve().relative_to(sites.resolve())
                    if site_folder.is_symlink() or file.is_symlink():
                        raise ValueError('Symlinks are not served.')
                    if file.stat().st_size>512000:raise ValueError('Site exceeds the supported size.')
                    source=file.read_bytes().decode('utf-8')
                    try:
                        metadata=json.loads((site_folder/'site.json').read_text(encoding='utf-8'))
                        title=metadata.get('title','Synthetix page') if isinstance(metadata,dict) else 'Synthetix page'
                    except (OSError,ValueError):title='Synthetix page'
                    document=isolated_document(source,str(title)[:120]).encode('utf-8')
                except (OSError, ValueError):
                    self.send_body(404, b'Site not found.', 'text/plain; charset=utf-8')
                    return
                self.send_body(200, document, 'text/html; charset=utf-8')
                return
            self.send_body(404, b'Not found.', 'text/plain; charset=utf-8')

        def do_POST(self):
            if not self.valid_host():return
            if (urlsplit(self.path).path == '/_synthetix_stop'
                    and self.authorized()):
                self.send_body(200, b'Stopping local host.', 'text/plain; charset=utf-8')
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_body(403, b'Forbidden.', 'text/plain; charset=utf-8')
    return Handler


def serve(sites, state, port=0):
    sites.mkdir(parents=True, exist_ok=True)
    state.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(sites, token))
    record = {'pid': os.getpid(), 'port': server.server_port, 'token': token,
              'started_at': datetime.now(timezone.utc).isoformat()}
    temporary = state.with_name(state.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(record), encoding='utf-8')
    temporary.replace(state)
    print(f'Local site host ready on 127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sites', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    arguments = parser.parse_args()
    serve(arguments.sites.resolve(), arguments.state.resolve(), arguments.port)
