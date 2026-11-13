"""Find typed channel and component roles without a project role list."""
import re


def discover(db, cid, signals, ports):
    roles, contracts = [], []
    by_path = {s.path: s for s in signals}
    by_name = {s.name: s for s in signals}
    for bid, path, cls in db.q('SELECT id,path,class_name FROM bundles WHERE component_id=?', (cid,)):
        if not cls or not re.search(r'(?:^|[.$])(Stream|Flow)(?:$|\[)', cls):
            continue
        leaves = {s.path[len(path)+1:]: s for s in signals if s.path.startswith(path + '.') or s.path.startswith(path + '/')}
        # Some database paths flatten the bundle name into the leaf RTL name.
        prefix = path.rsplit('/', 1)[-1].replace('.', '_')
        if not leaves:
            leaves = {n[len(prefix)+1:]: s for n,s in by_name.items() if n.startswith(prefix+'_')}
        valid, ready = leaves.get('valid'), leaves.get('ready')
        payload = [s for n,s in leaves.items() if n.startswith('payload')]
        row = {'role': 'handshake' if 'Stream' in cls else 'flow', 'path': path, 'evidence': {'bundle_id': bid, 'spinal_type': cls}, 'checks': []}
        if valid and ready and valid.width == ready.width == 1 and valid.name in ports and ready.name in ports and payload and all(s.name in ports for s in payload):
            # Check the producer only. Input producers are environment obligations.
            if ports[valid.name]['direction'] == 'output' and all(ports[s.name]['direction'] == 'output' for s in payload):
                for signal in payload:
                    prop = {'id': f'stream_{bid}_{signal.id}', 'kind': 'stream_stability', 'valid': valid.name, 'ready': ready.name, 'signal': signal.name}
                    contracts.append(prop); row['checks'].append(prop['id'])
        if not row['checks']:
            row['unsupported'] = 'producer payload/control ports unavailable or producer is environment input'
        roles.append(row)
    for signal in signals:
        if signal.type in ('UInt', 'SInt') and signal.kind == 'reg':
            assignments = db.q('SELECT id,source FROM assignments WHERE target_id=? AND kind=?', (signal.id, 'data'))
            updates = [(a,e) for a,e in assignments if re.search(r'(?<!\w)' + re.escape(signal.name) + r'\s*[+-]\s*\d+', e or '')]
            if updates:
                roles.append({'role': 'counter', 'path': signal.path, 'evidence': {'signal_id': signal.id, 'spinal_type': signal.type, 'assignments': [a for a,_ in updates]}, 'checks': [], 'unsupported': 'wrap and range requirements are not encoded; bit observations apply when exposed'})
    cls = db.q('SELECT class_name FROM components WHERE id=?', (cid,))[0][0] or ''
    memories = db.q('SELECT id,depth,width FROM memories WHERE component_id=?', (cid,))
    for role, pattern in [('fifo', r'(StreamFifo|FifoCC)'), ('arbiter', r'(StreamArbiter|Arbiter)'), ('cam', r'(Cam|CAM)')]:
        if re.search(pattern, cls):
            roles.append({'role': role, 'path': '', 'evidence': {'spinal_type': cls, 'memories': [dict(id=i, depth=d, width=w) for i,d,w in memories]}, 'checks': [], 'unsupported': 'semantic endpoint binding is not present in this database role'})
    return roles, contracts
