"""Register-to-register paths. This is a structural inventory, not a proof."""
from collections import defaultdict
import sqlite3


UNRUN = ["cdc.protocol", "cdc.metastability", "cdc.pulse_loss", "cdc.reconvergence",
         "cdc.async_fifo", "rdc.release", "rdc.reconvergence"]


def analyze(db):
    c = db.conn
    c.row_factory = sqlite3.Row
    domains = {r['id']: dict(r) for r in c.execute('SELECT * FROM clock_domains')}
    signals = {r['id']: dict(r) for r in c.execute(
        'SELECT s.*, f.path AS file FROM signals s LEFT JOIN files f ON f.id=s.file_id')}
    regs = {i: s for i, s in signals.items() if s['kind'] == 'reg' and not s['pruned']}
    incoming, outgoing = defaultdict(set), defaultdict(set)
    blackbox = False
    for src, dst, kind in c.execute('SELECT src,dst,kind FROM edges'):
        if kind == 'init':
            continue
        blackbox |= kind == 'blackbox'
        incoming[dst].add(src)
        outgoing[src].add(dst)
    findings, crossings = [], []

    def emit(rule, src, dst, message, severity='warning'):
        findings.append(dict(rule=rule, severity=severity, source=src['path'] if src else None,
                             endpoint=dst['path'], file=dst['file'], line=dst['line'], message=message))

    def clock(d):
        return (d.get('clock_key'), d.get('clock_edge'))

    used = {s['clock_domain_id'] for s in regs.values()}
    for i in sorted(used, key=str):
        d = domains.get(i, {})
        if not d.get('clock_key') or not d.get('clock_edge'):
            emit('cdc.unknown_domain', None, next(s for s in regs.values() if s['clock_domain_id'] == i),
                 'Clock identity or edge is unknown.')
    # One domain cannot have an inter-domain register path. Do not traverse its full graph.
    if len(used) > 1:
        for dst_id, dst in regs.items():
            pending, seen, sources = list(incoming[dst_id]), set(), set()
            while pending:
                node = pending.pop()
                if node in seen:
                    continue
                seen.add(node)
                if node in regs:
                    sources.add(node)
                else:
                    pending.extend(incoming[node])
            for src_id in sorted(sources):
                src = regs[src_id]
                a, b = domains.get(src['clock_domain_id'], {}), domains.get(dst['clock_domain_id'], {})
                if not a.get('clock_key') or not b.get('clock_key'):
                    continue
                if clock(a) == clock(b):
                    continue
                # A direct two-stage chain is only a candidate. Logic and fanout disqualify it.
                next_regs = outgoing[dst_id]
                chain = (src['width'] == dst['width'] == 1 and incoming[dst_id] == {src_id}
                         and len(next_regs) == 1 and all(n in regs and
                         regs[n]['clock_domain_id'] == dst['clock_domain_id'] and
                         incoming[n] == {dst_id} for n in next_regs))
                kind = 'sync_candidate' if chain else ('multi_bit' if max(src['width'], dst['width']) > 1 else 'unsynchronized')
                crossings.append(dict(source=src['path'], destination=dst['path'], kind=kind,
                                      relationship='unknown', source_domain=src['clock_domain_id'],
                                      destination_domain=dst['clock_domain_id']))
                emit('cdc.' + kind, src, dst,
                     'Structural synchronizer candidate; protocol unproved.' if chain else
                     'Crossing needs synchronization or a verified gray/handshake protocol.')
    warnings = [dict(r) for r in c.execute('SELECT * FROM warnings')]
    unknown_inputs = [s['path'] for s in signals.values() if s['direction'] == 'in' and not s['clock_role']]
    limitations = ['Primary input domains are not inferred.', 'Clock relationships between different keys are unknown.',
                   'Memory and blackbox internal crossings are not analyzed.']
    if blackbox or warnings or not regs:
        limitations.append('Incomplete structural evidence: blackbox edges, extractor warnings or no registers.')
    return dict(status='inconclusive', scope='register-boundary structural inventory',
                registers=len(regs), domains=list(domains.values()), clock_count=len({clock(domains[i]) for i in used if i in domains}),
                crossings=crossings, findings=findings, extractor_warnings=warnings,
                unclassified_inputs=unknown_inputs, limitations=limitations,
                rules=[{'id': rule, 'status': 'not_run'} for rule in UNRUN],
                structural_status='findings' if findings else ('no_checks' if not regs else 'no_crossings_found'))
