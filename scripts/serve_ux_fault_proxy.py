"""Loopback-only browser UX fault injection. Never runs or mutates simulation jobs.

Start a separate Vite server with GSM_API_PROXY pointing at this proxy. Set
--control to a local JSON file containing {"mode": "asset-missing"}. Modes:
pass, api-unavailable, asset-missing, queued, router-unavailable, interrupted.
GET requests otherwise forward to an existing local API. POST requests are
synthetic responses only and are NEVER forwarded. Not a performance benchmark.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8014)
    parser.add_argument('--target-port', type=int, default=8013)
    parser.add_argument('--control', type=Path, default=Path('build/m4-ux/fault.json'))
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, payload, content_type='application/json'):
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def mode(self):
            try:
                return json.loads(args.control.read_text(encoding='utf-8-sig'))['mode']
            except (OSError, ValueError, KeyError):
                return 'pass'

        def fault(self):
            mode = self.mode()
            if mode == 'asset-missing' and self.path.startswith('/api/regions/nvmr-hanoi-core/map/streets'):
                self.respond(404, {'error': {'code': 'UX_FAULT_ASSET', 'message': 'Injected missing streets GeoJSON'}})
                return True
            if mode == 'proxy-unavailable' and (self.path.startswith('/api/v3/simulation/jobs') or self.path=='/api/health'):
                self.respond(502, b'Injected Vite proxy connection failure', 'text/plain')
                return True
            if not self.path.startswith('/api/v3/simulation/jobs'):
                return False
            if mode == 'api-unavailable':
                self.respond(503, {'error': {'code': 'UX_FAULT_API', 'message': 'Injected simulation API outage; map assets remain accessible'}})
                return True
            if mode in ('queued', 'router-unavailable', 'interrupted'):
                if self.path.endswith('/runtime'):
                    self.respond(200, {'application':'gsm-map-sandbox','worker':'offline','syntheticFaultInjection':True})
                    return True
                cancelled = self.path.endswith('/cancel')
                status = 'CANCELLED' if cancelled else {'queued': 'QUEUED', 'router-unavailable': 'FAILED', 'interrupted': 'INTERRUPTED'}[mode]
                error = {'code': 'MODE_NOT_READY', 'message': 'UX_FAULT_INJECTION: Hanoi router/graph unavailable'} if mode == 'router-unavailable' else None
                self.respond(200, {'id': 'ux-fault-injection', 'status': status, 'progress': 0, 'error': error, 'syntheticFaultInjection': True})
                return True
            return False

        def do_GET(self):
            if self.fault():
                return
            if not self.path.startswith('/api/'):
                self.respond(404, {'error': {'code': 'API_ONLY', 'message': 'Local QA API proxy only'}})
                return
            try:
                with urlopen(f'http://127.0.0.1:{args.target_port}{self.path}', timeout=20) as response:
                    self.respond(response.status, response.read(), response.headers.get('Content-Type', 'application/json'))
            except HTTPError as exc:
                self.respond(exc.code, exc.read())
            except (URLError, TimeoutError) as exc:
                self.respond(502, {'error': {'code': 'QA_TARGET_UNAVAILABLE', 'message': str(exc)}})

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if not self.fault():
                self.respond(405, {'error': {'code': 'QA_READ_ONLY', 'message': 'POST is never forwarded; choose a synthetic fault mode'}})

    print(f'UX fault injection proxy: http://127.0.0.1:{args.port}; control={args.control}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
