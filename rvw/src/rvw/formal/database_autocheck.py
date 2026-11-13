"""Read port and enum candidates from a frozen SpinalDB database."""
import re
from rvw.query.db import DesignDB


def enum_states(text):
    if not text or '$incomplete:' in text or '{h:' in text:
        return None
    match = re.fullmatch(r'.+@.+\[\d+\]\{(.+)\}', text)
    if not match:
        return None
    states = []
    for item in match[1].split(','):
        value = item.rsplit('=', 1)
        if len(value) != 2 or not re.fullmatch(r'[0-9a-f]+', value[1]):
            return None
        states.append(int(value[1], 16))
    return sorted(set(states))


def populate(plan, database, capture):
    db = DesignDB(database, capture=capture)
    try:
        from rvw.query.db import SCHEMA
        if db.schema != SCHEMA:
            raise ValueError('autocheck needs a current SpinalDB database')
        components = db.q('SELECT id, path FROM components WHERE module=?', (plan['top'],))
        requested = plan.get('database_component')
        if requested is not None:
            components = [c for c in components if c[1] == requested]
        if len(components) != 1:
            raise ValueError('database module needs a unique component; set database_component')
        cid, path = components[0]
        signals = db.signals_where('s.component_id=?', (cid,))
        ports = {s.name: {'direction': {'in': 'input', 'out': 'output'}[s.direction], 'width': s.width}
                 for s in signals if s.direction in ('in', 'out') and not s.pruned}
        if plan.get('ports') and plan['ports'] != ports:
            raise ValueError('declared ports differ from database module ports')
        fsms, skipped, internal = [], [], {}
        contracts = list(plan.get('contracts', []))
        for signal in signals:
            states = enum_states(signal.type)
            if states is None:
                if '@' in (signal.type or ''):
                    skipped.append({'signal': signal.path, 'reason': 'enum encoding unavailable'})
                continue
            if signal.name not in ports or ports[signal.name]['direction'] != 'output':
                if signal.pruned or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', signal.name):
                    skipped.append({'signal': signal.path, 'reason': 'internal enum lacks a plain retained RTL name'})
                    continue
                internal[signal.name] = signal.width
                ports[signal.name] = {'direction': 'output', 'width': signal.width}
            if len(states) > 1 and all(v >= 0 and (v & (v-1)) == 0 for v in states):
                contracts.append({'id': f'onehot_{signal.name}', 'kind': 'mutex' if 0 in states else 'onehot', 'signal': signal.name})
            fsms.append({'signal': signal.name, 'states': states,
                         'transitions': [[a, b] for a in states for b in states]})
        by_name = {s.name: s for s in signals}
        by_id = {s.id: s for s in signals}
        for aid, expression, target_id, target_range in db.q('SELECT id, source, target_id, range FROM assignments WHERE component_id=? AND cond_id IS NULL AND kind=?', (cid, 'data')):
            match = re.fullmatch(r'\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*([+-])\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?', expression or '')
            if match and match[1] in ports and match[3] in ports and ports[match[1]]['width'] == ports[match[3]]['width']:
                left, right = by_name[match[1]], by_name[match[3]]
                target = by_id.get(target_id)
                if target and not target_range and target.width == left.width and target.type == left.type == right.type and left.type in ('UInt', 'SInt'):
                    contracts.append({'id': f'overflow_assignment_{aid}', 'kind': 'arithmetic_overflow',
                                      'signal': left.name, 'other': right.name, 'signed': left.type == 'SInt',
                                      'operation': 'add' if match[2] == '+' else 'sub'})
        for pid, address, enable, depth in db.q('SELECT p.id,p.address,p.enable,m.depth FROM mem_ports p JOIN memories m ON m.id=p.memory_id WHERE p.component_id=?', (cid,)):
            if type(depth) is int and depth > 0 and address in ports and depth <= 2**ports[address]['width'] and (enable in (None, '1') or enable in ports and ports[enable]['width'] == 1):
                contracts.append({'id': f'array_port_{pid}', 'kind': 'array_bound', 'signal': address,
                                  'enable': enable or '1', 'size': depth})
            else:
                skipped.append({'memory_port': pid, 'reason': 'address or enable needs RTL exposure or expression lowering'})
        from .role_discovery import discover
        roles, discovered = discover(db, cid, signals, ports)
        contracts.extend(discovered)
        roles.extend({'role': 'fsm', 'path': f['signal'], 'evidence': {'encoding': f['states']}, 'checks': ['fsm_state', 'fsm_transition']} for f in fsms)
        return dict(plan, internal_ports=internal, ports=ports, fsms=fsms, contracts=contracts, toggle=plan.get('toggle', True), source_locations={s.name: {'file': s.file, 'line': s.line} for s in signals if s.file and s.line}, module=plan['top']), {
            'component': path, 'roles': roles, 'skipped': skipped, 'staleness': db.staleness(),
            'scope': 'Port inventory and complete enum encodings from SpinalDB. Exact retained internal enum names are exposed and width-checked before proof.'}
    finally:
        db.close()
