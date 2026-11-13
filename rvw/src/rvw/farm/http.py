"""Small authenticated HTTP queue service. Tokens map to service owners."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import Queue

PAGE = '''<!doctype html><meta charset="utf-8"><title>Regression service</title>
<h1>Regression service</h1><p>Collection complete does not mean DUT pass.</p>
<label>Token <input id="token" type="password"></label><button id="load">Refresh</button>
<pre id="runs"></pre><script>
load.onclick=async()=>{let r=await fetch('/runs',{headers:{Authorization:'Bearer '+token.value}});
runs.textContent=JSON.stringify(await r.json(),null,2)};
</script>'''


def server(root, tokens, host='127.0.0.1', port=8765):
    if not tokens or any(not k or not v for k, v in tokens.items()):
        raise ValueError('provide token-to-owner mappings')
    queue = Queue(root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, data, content='application/json'):
            body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def owner(self):
            supplied = self.headers.get('Authorization', '').removeprefix('Bearer ')
            return next((owner for token, owner in tokens.items() if hmac.compare_digest(token, supplied)), None)

        def do_GET(self):
            if self.path == '/':
                return self.respond(200, PAGE, 'text/html; charset=utf-8')
            owner = self.owner()
            if not owner:
                return self.respond(401, {'error': 'authentication required'})
            if self.path == '/runs':
                return self.respond(200, queue.jobs(owner))
            return self.respond(404, {'error': 'unknown endpoint'})

        def do_POST(self):
            owner = self.owner()
            if not owner:
                return self.respond(401, {'error': 'authentication required'})
            try:
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                if self.path == '/runs':
                    data.pop('owner', None)
                    return self.respond(201, queue.submit(owner, **data))
                if self.path.startswith('/cancel/'):
                    return self.respond(200, queue.cancel(self.path.split('/')[-1], owner))
                self.respond(404, {'error': 'unknown endpoint'})
            except (ValueError, TypeError, StopIteration) as exc:
                self.respond(400, {'error': str(exc)})
    return ThreadingHTTPServer((host, port), Handler)
