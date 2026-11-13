"""Small authenticated HTTP queue service. Tokens map to service owners."""
import hmac
import json
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import Queue

PAGE = '''<!doctype html><meta charset="utf-8"><title>Regression service</title>
<style>body{font:15px system-ui;max-width:1100px;margin:30px auto}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}button{margin:5px}pre{white-space:pre-wrap}svg{width:100%;height:150px}</style>
<h1>Regression service</h1><p>Execution complete does not mean DUT pass. Missing samples stay absent.</p>
<label>Token <input id="token" type="password"></label><button id="refresh">Refresh</button>
<h2>Runs</h2><div id="runs"></div><h2>Recorded pass rate</h2><svg id="chart" viewBox="0 0 1000 100" role="img" aria-label="Recorded pass rate by run"></svg>
<h2>Failure clusters</h2><div id="clusters"></div><h2>Per-test history</h2><div id="history"></div><pre id="detail"></pre>
<script>
const byId=id=>document.getElementById(id);
async function get(path){let r=await fetch(path,{headers:{Authorization:'Bearer '+byId('token').value}});if(!r.ok)throw Error(await r.text());return r.json()}
function table(target,heads,rows){target.replaceChildren();let t=document.createElement('table');for(let row of [heads,...rows]){let tr=t.insertRow();for(let text of row)tr.insertCell().textContent=text}target.append(t)}
byId('refresh').onclick=async()=>{try{let d=await get('/snapshot');
table(byId('runs'),['Run','State','Tests','Passes','C3 evidence','Recorded gate'],d.runs.map(r=>[r.id,r.state,r.tests,r.passes,r.evidence,r.recorded_gate||'not recorded']));
let chart=byId('chart');chart.replaceChildren();let prev=null;d.trends.forEach((r,i)=>{if(r.pass_rate===null){prev=null;return}let x=10+i*980/Math.max(1,d.trends.length-1),y=90-r.pass_rate*80;
if(prev){let l=document.createElementNS('http://www.w3.org/2000/svg','line');for(let [k,v]of Object.entries({x1:prev[0],y1:prev[1],x2:x,y2:y,stroke:'steelblue'}))l.setAttribute(k,v);chart.append(l)}
let c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r',3);chart.append(c);prev=[x,y]});
let clusters=byId('clusters');clusters.replaceChildren();for(let c of d.failure_clusters){let p=document.createElement('p');p.textContent=c.category+' / '+c.signature+' / '+c.members.length+' observations';clusters.append(p);for(let path of c.bundles){let b=document.createElement('button');b.textContent='Open C5 bundle';b.onclick=async()=>byId('detail').textContent=JSON.stringify(await get('/bundle/'+c.job_id+'?path='+encodeURIComponent(path)),null,2);clusters.append(b)}}
table(byId('history'),['Test / seed','Outcomes'],Object.entries(d.test_history).map(([k,v])=>[JSON.parse(k).join(' / '),v.map(x=>x.status+(x.conclusive?'':' (inconclusive)')).join(' → ')]));
}catch(e){byId('detail').textContent=e.message}};
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
            path = urlsplit(self.path)
            if path.path == '/snapshot':
                from .live import snapshot
                return self.respond(200, snapshot(queue, owner))
            if path.path.startswith('/bundle/'):
                from .live import bundle
                try:
                    relative = parse_qs(path.query).get('path', [''])[0]
                    return self.respond(200, bundle(queue, owner, path.path.split('/')[-1], relative))
                except (ValueError, OSError) as exc:
                    return self.respond(400, {'error': str(exc)})
            if path.path == '/runs':
                return self.respond(200, queue.jobs(owner))
            if path.path == '/events':
                try:
                    after = int(parse_qs(path.query).get('after', [self.headers.get('Last-Event-ID', 0)])[0])
                except ValueError:
                    return self.respond(400, {'error': 'invalid event cursor'})
                owned = {j['id'] for j in queue.jobs(owner)}
                events = [e for e in queue.events(after) if e.get('job_id') in owned or e.get('owner') == owner]
                body = ''.join('id: ' + str(e['seq']) + '\ndata: ' + json.dumps(e) + '\n\n' for e in events)
                return self.respond(200, body or ': no new events\n\n', 'text/event-stream')
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
                if self.path == '/workflows':
                    from .workflows import workflow
                    data.pop('owner', None)
                    return self.respond(200, workflow(str(queue.root), owner=owner, **data))
                if self.path.startswith('/cancel/'):
                    return self.respond(200, queue.cancel(self.path.split('/')[-1], owner))
                self.respond(404, {'error': 'unknown endpoint'})
            except (ValueError, TypeError, StopIteration) as exc:
                self.respond(400, {'error': str(exc)})
    return ThreadingHTTPServer((host, port), Handler)
