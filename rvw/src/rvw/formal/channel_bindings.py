"""Resolve typed channel ports and clock-domain metadata in a captured SpinalDB."""
from .property_library import ident
from .temporal import Unsupported


def bind_database(report, contracts, db):
    if report.get('schema') != 'rvw.checks/1':
        raise ValueError('expected rvw.checks/1')
    result = {}
    for channel in report.get('channels', []):
        key = channel['path'] + '.' + channel['object']
        contract = dict(contracts.get(key, {}))
        paths = [channel['valid'], *([channel['ready']] if channel.get('ready') else []), *channel.get('payload', [])]
        signals = {p: db.resolve_one(p) for p in paths}
        owners = {s.component_id for s in signals.values()}
        if len(owners) != 1 or any(s.direction not in ('in', 'out') or s.pruned for s in signals.values()):
            raise Unsupported('channel_local_ports', key)
        owner = next(iter(owners))
        ports = {path: ident(signal.name) for path, signal in signals.items()}
        if len(set(ports.values())) != len(ports):
            raise Unsupported('channel_port_collision', key)
        domains = {s.clock_domain_id for s in signals.values() if s.clock_domain_id is not None}
        anchor = contract.get('domain_signal')
        if anchor:
            signal = db.resolve_one(anchor)
            if signal.component_id != owner or signal.clock_domain_id is None:
                raise Unsupported('channel_domain_anchor', anchor)
            domains.add(signal.clock_domain_id)
        if len(domains) != 1:
            raise Unsupported('channel_clock_binding', key)
        domain = db.clock_domain(next(iter(domains)))
        if not domain or domain.get('edge') not in ('RISING', 'rising', 'posedge'):
            raise Unsupported('channel_clock_edge', key)
        if domain.get('clock_enable') or domain.get('soft_reset'):
            raise Unsupported('channel_domain_controls', key)
        def local_control(path):
            root = db.resolve_one(path)
            if root.component_id == owner:
                return root
            candidates = []
            for port in db.signals_where("s.component_id=? AND s.direction='in'", (owner,)):
                sources = db.q('SELECT source FROM assignments WHERE target_id=?', (port.id,))
                reads = db.q("SELECT src FROM edges WHERE dst=? AND kind='data'", (port.id,))
                if sources == [(root.name,)] and reads == [(root.id,)]:
                    candidates.append(port)
            if len(candidates) != 1:
                raise Unsupported('channel_control_port', path)
            return candidates[0]
        clock = local_control(domain['clock'])
        if clock.component_id != owner or clock.direction != 'in' or clock.width != 1 or clock.pruned:
            raise Unsupported('channel_clock_port', key)
        if channel['kind'].lower() not in ('stream', 'flow'):
            raise Unsupported('channel_type', channel['kind'])
        if any(signals[p].width != 1 for p in paths[:2 if channel.get('ready') else 1]):
            raise Unsupported('channel_control_width', key)
        contract.update(id=contract.get('id', ident(channel['object'])), clock=ident(clock.name), ports=ports,
                        widths={p: s.width for p,s in signals.items()})
        payload = channel.get('payload', [])
        if len(payload) == 1:
            contract['width'] = signals[payload[0]].width
        if domain.get('reset'):
            reset = local_control(domain['reset'])
            if reset.component_id != owner or reset.direction != 'in' or reset.width != 1 or reset.pruned:
                raise Unsupported('channel_reset_port', key)
            contract.update(reset=ident(reset.name), reset_active=domain['reset_active'])
        else:
            contract.pop('reset', None)
        result[key] = contract
    return result
