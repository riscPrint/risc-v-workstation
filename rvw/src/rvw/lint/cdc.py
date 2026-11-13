"""Clock inference, synchronizer recognition and crossing classes on SpinalDB data.

Recognized structures are candidates. Gray and data-stability needs become proof obligations
for `rvw formal` or simulation; a structural match is never a protocol proof."""
import re


LIBRARY = {  # Spinal library classes (last name segment) and what they implement
    'BufferCC': 'buffer_cc', 'StreamCCByToggle': 'toggle_handshake', 'FlowCCByToggle': 'toggle_handshake',
    'PulseCCByToggle': 'pulse_sync', 'StreamFifoCC': 'async_fifo', 'DataCC': 'handshake',
    'FlowCCUnsafeByToggle': 'toggle_handshake', 'ResetCtrl': 'reset_synchronizer',
}
MAX_STAGES = 6


def _args(text):
    """Top-level comma-separated arguments of the call that starts at text[0] == '('."""
    depth, out, cur = 0, [], ''
    for ch in text:
        if ch == '(':
            depth += 1
            if depth == 1:
                continue
        elif ch == ')':
            depth -= 1
            if depth == 0:
                out.append(cur)
                return out
        elif ch == ',' and depth == 1:
            out.append(cur)
            cur = ''
            continue
        cur += ch
    return None


def is_gray(key, w):
    """True when a typed key is binary ^ (binary >> 1), in either operand order."""
    m = re.match(r'^ := (?:CastUIntToBits\[\d+\]\()?Operator\$UInt\$Xor\[\d+\]', key or '')
    if not m:
        return False
    args = _args(key[m.end():])
    if not args or len(args) != 2:
        return False
    for x, sh in (args, args[::-1]):
        if not re.fullmatch(r'[^(), ]+:UInt\[\d+\]', x):
            continue
        if sh in (f'Operator$UInt$ShiftRightByIntFixedWidth<1>[{w}]({x})',) or re.fullmatch(
                rf'Operator\$UInt\$ShiftRightByUInt\[\d+\]\({re.escape(x)},lit:UIntLiteral\[\d+\]=1\)', sh):
            return True
    return False


def gray_key(design, node, hops=3):
    """The typed key when a register holds binary ^ (binary >> 1), directly or through a
    copied wire, else None."""
    rows = [a for a in design.assignments(node) if a['kind'] != 'init']
    # One data assignment: the register holds or takes the new code (an enable keeps it Gray).
    if len(rows) != 1 or rows[0]['range']:
        return None
    key = rows[0]['key'] or ''
    if is_gray(key, design.signals[node]['width']):
        return key
    inputs = {r[0] for r in design.c.execute(
        "SELECT signal_id FROM assign_reads WHERE assignment_id=? AND kind='data'", (rows[0]['id'],))}
    if hops and len(inputs) == 1 and re.fullmatch(r' := [^(), ]+:\w+\[\d+\]', key):
        src = next(iter(inputs))
        if src not in design.regs and design.signals[src]['width'] == design.signals[node]['width']:
            return gray_key(design, src, hops - 1)
    return None


class Clocks:
    """Clock inference: primary, divided, gated, generated (blackbox) or unknown."""

    def __init__(self, design, intent):
        self.d = design
        self.info = {}
        roles = {i for i, s in design.signals.items() if s.get('clock_role') == 'clock'}
        clock_nets = roles | {design.by_path[x['clock']] for x in design.domains.values()
                              if x.get('clock') in design.by_path}
        for did, dom in design.domains.items():
            root = design.by_path.get(dom.get('clock'))
            row = dict(domain=did, clock=dom.get('clock'), clock_key=dom.get('clock_key'),
                       edge=dom.get('clock_edge'), kind='unknown', parent=None)
            if root is not None:
                internal, leaves = design.cone(root)
                regs = [n for n in leaves if n in design.regs]
                boxes = [n for n in leaves if self._blackbox_output(n)]
                clocks = [n for n in leaves if n in clock_nets]
                single = all(len(design.incoming[n]) <= 1 for n in internal | {root})
                if self._blackbox_output(root) or (boxes and not regs):
                    row.update(kind='generated', source=design.signals[boxes[0] if boxes else root]['path'])
                elif not design.incoming[root] or (single and len(leaves) == 1 and not regs and not boxes):
                    src = root if not design.incoming[root] else next(iter(leaves))
                    row.update(kind='primary' if design.is_top_input(src) else 'unknown', source=design.signals[src]['path'])
                elif regs:
                    r = regs[0]
                    toggles = design.upstream_regs(r) == {r} and design.signals[r]['width'] == 1
                    row.update(kind='divided', source=design.signals[r]['path'],
                               parent_domain=design.signals[r]['clock_domain_id'], divide_by=2 if toggles else None)
                elif clocks and len(leaves) > 1:
                    c = clocks[0]
                    row.update(kind='gated', source=design.signals[c]['path'],
                               enables=sorted(design.signals[n]['path'] for n in leaves if n != c))
            self.info[did] = row
        for row in self.info.values():
            row['master'] = self._master(row, set())
        groups = intent.get('clocks', [])
        if not isinstance(groups, list) or any(
                not isinstance(g, dict) or set(g) != {'clocks', 'relationship', 'reason'}
                or g['relationship'] not in ('synchronous', 'asynchronous') or not isinstance(g['clocks'], list)
                or len(g['clocks']) < 2 or not str(g['reason']).strip() for g in groups):
            raise ValueError('intent.clocks rows need clocks (2+), relationship synchronous|asynchronous and reason')
        known = {r['clock'] for r in self.info.values()}
        for g in groups:
            for c in g['clocks']:
                if c not in known:
                    raise ValueError(f'intent.clocks names an unknown clock: {c}')
        self.groups = groups

    def _blackbox_output(self, n):
        s = self.d.signals[n]
        comp = self.d.components.get(s['component_id'], {})
        return bool(comp.get('blackbox')) and s['direction'] == 'out'

    def _master(self, row, seen):
        if row['domain'] in seen:
            return None
        seen.add(row['domain'])
        if row['kind'] == 'primary':
            return row['source']
        if row['kind'] == 'divided':
            parent = self.info.get(row.get('parent_domain'))
            return self._master(parent, seen) if parent else None
        if row['kind'] == 'gated':
            src = row['source']
            parent = next((r for r in self.info.values() if r['clock'] == src), None)
            if parent and parent is not row:
                return self._master(parent, seen)
            i = self.d.by_path.get(src)
            return src if i is not None and self.d.is_top_input(i) else None
        return None

    def relationship(self, a, b):
        x, y = self.info.get(a), self.info.get(b)
        if not x or not y or not x['clock_key'] or not y['clock_key']:
            return 'unknown'
        if (x['clock_key'], x['edge']) == (y['clock_key'], y['edge']):
            return 'same'
        for g in self.groups:
            if x['clock'] in g['clocks'] and y['clock'] in g['clocks']:
                return 'declared_' + g['relationship']
        if x['master'] and x['master'] == y['master']:
            return 'related'
        if x['master'] and y['master']:
            return 'asynchronous'
        return 'unknown'


class Crossings:
    def __init__(self, design, clocks):
        self.d, self.clocks = design, clocks

    def simple_up(self, node):
        """The register that drives `node` through single-input wires, else None."""
        inputs = self.d.incoming[node]
        while len(inputs) == 1:
            n = next(iter(inputs))
            if n in self.d.regs:
                return n
            if self.d.signals.get(n, {}).get('kind') in ('mem', 'mem_read'):
                return None
            inputs = self.d.incoming[n]
        return None

    def simple_down(self, node):
        outs = self.d.outgoing[node]
        while len(outs) == 1:
            n = next(iter(outs))
            if n in self.d.regs:
                return n
            outs = self.d.outgoing[n]
        return None

    def stages(self, first):
        f = self.d.regs[first]
        stages, cur = [first], first
        while len(stages) < MAX_STAGES:
            nxt = self.simple_down(cur)
            if (nxt is None or self.d.regs[nxt]['clock_domain_id'] != f['clock_domain_id']
                    or self.d.regs[nxt]['width'] != f['width'] or self.simple_up(nxt) != cur):
                break
            stages.append(nxt)
            cur = nxt
        return stages

    def first_stage_fanout(self, first):
        if len(self.d.outgoing[first]) <= 1:
            return False
        found, _ = self.d.fanout(first)
        return any(self.d.regs[r]['clock_domain_id'] == self.d.regs[first]['clock_domain_id']
                   and r != first for r in found) and len(found | self.d.outgoing[first]) > 1

    def library(self, node):
        for path, cls in self.d.component_classes(node):
            name = cls.rsplit('.', 1)[-1].split('$')[0]
            if name in LIBRARY:
                return dict(component=path, class_name=cls, kind=LIBRARY[name])
        return None


def tagged(signal):
    return 'crossClockDomain' in (signal.get('tags') or '')


def analyze(design, emit, intent, pairs):
    """`pairs` are (source register, destination register) with different clock records."""
    clocks = Clocks(design, intent)
    x = Crossings(design, clocks)
    regs = design.regs
    rows = []
    for src_id, dst_id in pairs:
        src, dst = regs[src_id], regs[dst_id]
        rel = clocks.relationship(src['clock_domain_id'], dst['clock_domain_id'])
        stages = x.stages(dst_id)
        rows.append(dict(src=src_id, dst=dst_id, relationship=rel, stages=stages,
                         direct=x.simple_up(dst_id) == src_id, library=x.library(dst_id),
                         fanout=x.first_stage_fanout(dst_id)))
    sync_ends = {r['stages'][-1] for r in rows if len(r['stages']) >= 2 and regs[r['dst']]['width'] == 1}
    crossings, obligations = [], []
    for r in rows:
        src, dst = regs[r['src']], regs[r['dst']]
        width = max(src['width'] or 1, dst['width'] or 1)
        n = len(r['stages'])
        out = dict(source=src['path'], destination=dst['path'], relationship=r['relationship'],
                   source_domain=src['clock_domain_id'], destination_domain=dst['clock_domain_id'],
                   stages=[regs[i]['path'] for i in r['stages']], library=r['library'], width=width)
        sev, extra = 'warning', {}
        if r['relationship'] in ('related', 'declared_synchronous'):
            kind, rule, sev = 'synchronous_related', 'cdc.related_clock_crossing', 'info'
            msg = 'Clocks share a source or are declared synchronous. Timing analysis covers this path.'
        elif not r['direct'] and (n >= 2 or tagged(dst)):
            kind, rule, sev = 'glitch_before_sync', 'cdc.comb_before_sync', 'error'
            msg = 'Combinational logic drives a synchronizer input. A glitch can be captured.'
        elif r['fanout'] and (n == 1) and (tagged(dst) or width == 1):
            kind, rule, sev = 'first_stage_fanout', 'cdc.sync_stage_fanout', 'error'
            msg = 'The first synchronizer stage drives more than the next stage. Its value can be metastable.'
        elif width == 1 and n >= 2:
            kind, rule = f'sync_{n}ff', 'cdc.sync_candidate'
            msg = f'Structural {n}-stage synchronizer candidate; protocol unproved.'
        elif n >= 2 and gray_key(design, r['src']):
            kind, rule, sev = 'gray_sync', 'cdc.gray_candidate', 'info'
            msg = 'Multi-bit synchronizer with a Gray-encoded source. One-bit change per update is a proof obligation.'
            obligations.append(dict(kind='gray_code', id=f'gray_{len(obligations)}', signal=src['path'],
                                    width=width, clock_domain=src['clock_domain_id'], destination=dst['path']))
            extra['obligation'] = obligations[-1]['id']
        else:
            qualifiers = sorted(design.signals[i]['path'] for i in design.upstream_regs(r['dst']) & sync_ends
                                if i != r['dst'])
            if width > 1 and qualifiers:
                kind, rule, sev = 'qualified_data', 'cdc.qualified_data_candidate', 'info'
                msg = 'Multi-bit data is sampled under a synchronized qualifier. Data stability is a proof obligation.'
                # The qualifier's source register is in the data source's domain.
                q_src = [regs[c['src']]['path'] for c in rows if c['stages'] and
                         regs[c['stages'][-1]]['path'] in qualifiers]
                obligations.append(dict(kind='data_stable', id=f'stable_{len(obligations)}', signal=src['path'],
                                        width=width, qualifier=q_src[0] if q_src else None,
                                        clock_domain=src['clock_domain_id'], destination=dst['path']))
                extra.update(obligation=obligations[-1]['id'], qualifiers=qualifiers)
            elif width > 1:
                kind, rule = 'multi_bit', 'cdc.multi_bit'
                msg = 'Multi-bit crossing needs a Gray code, handshake or qualifier. Bits can arrive in different cycles.'
            else:
                kind, rule = 'unsynchronized', 'cdc.unsynchronized'
                msg = 'Crossing needs synchronization or a verified gray/handshake protocol.'
        if r['library'] and kind in ('multi_bit',) and r['library']['kind'] == 'buffer_cc':
            msg = 'BufferCC on a multi-bit value without a Gray-encoded source. ' + msg
        out.update(kind=kind, **extra)
        crossings.append(out)
        f = emit(rule, src, dst, msg, severity=sev)
        if r['library']:
            f['library'] = r['library']['class_name']
    # One source sampled by several destination registers of one clock: the copies can disagree.
    by_target = {}
    for c in crossings:
        if c['kind'] != 'synchronous_related':
            by_target.setdefault((c['source'], c['destination_domain']), []).append(c)
    for (source, _), group in sorted(by_target.items()):
        if len(group) > 1:
            f = emit('cdc.fanout_before_sync', regs[design.by_path[source]], regs[design.by_path[group[0]['destination']]],
                     'One source crosses into several registers of one clock. The copies can disagree for a cycle.')
            f['destinations'] = [g['destination'] for g in group]
    for ob in obligations:
        ob.update(bind_obligation(design, ob))
    memories = memory_crossings(design, clocks, x, emit)
    return dict(clocks=list(clocks.info.values()), crossings=crossings, obligations=obligations,
                memories=memories, clock_groups=clocks.groups,
                scope='structural classes; obligations are unproved until a formal or simulation run checks them')


def memory_crossings(design, clocks, x, emit):
    out = []
    for m in design.c.execute('SELECT m.*, s.path AS spath FROM memories m JOIN signals s ON s.id=m.signal_id'):
        ports = [dict(p) for p in design.c.execute('SELECT * FROM mem_ports WHERE memory_id=?', (m['id'],))]
        writes = {p['clock_domain_id'] for p in ports if p['kind'] in ('write', 'read_write')}
        reads = {p['clock_domain_id'] for p in ports if p['kind'] in ('read_sync', 'read_write')}
        pairs = {(a, b) for a in writes for b in reads if clocks.relationship(a, b) not in ('same', 'related', 'declared_synchronous')}
        if not pairs:
            continue
        lib = x.library(m['signal_id'])
        row = dict(memory=m['spath'], domains=[list(p) for p in sorted(pairs)], library=lib)
        out.append(row)
        sig = design.signals[m['signal_id']]
        if lib and lib['kind'] == 'async_fifo':
            emit('cdc.async_fifo_candidate', None, sig,
                 f"{lib['class_name']} memory crosses clocks. Pointer Gray coding and full/empty logic are unproved.",
                 severity='info')
        else:
            emit('cdc.memory_crossing', None, sig,
                 'Memory is written and read in different clocks. Address and data stability are unproved.')
    return out


def hierarchy(design, findings):
    """Findings and crossings grouped by the destination's component path."""
    comp_of = {s['path']: design.component_path(i) for i, s in design.signals.items()}
    rows = {}
    for f in findings:
        comp = comp_of.get(f.get('endpoint'), '')
        r = rows.setdefault(comp or '', dict(component=comp or '', findings=0, rules={}))
        r['findings'] += 1
        r['rules'][f['rule']] = r['rules'].get(f['rule'], 0) + 1
    return [rows[k] for k in sorted(rows)]


def local_clock(design, domain_id, component_id):
    """The clock net of a domain as seen inside one component, else None."""
    d = design.domains.get(domain_id) or {}
    root = design.by_path.get(d.get('clock'))
    if root is None:
        return None
    _, seen = design.fanout(root)
    names = sorted((design.signals[i]['clock_role'] != 'clock', design.signals[i]['name'])
                   for i in seen | {root} if design.signals[i]['component_id'] == component_id)
    return names[0][1] if names else None


def bind_obligation(design, ob):
    """Module, local names and clock for one obligation; `bind: null` with a reason when unknown."""
    i = design.by_path[ob['signal']]
    s = design.signals[i]
    comp = design.components.get(s['component_id']) or {}
    module = comp.get('module') or (comp.get('name') if comp.get('depth') == 0 else None)
    clock = local_clock(design, ob['clock_domain'], s['component_id'])
    ports = dict(clk=clock, value=s['name'])
    reason = None
    if ob['kind'] == 'data_stable':
        q = design.by_path.get(ob.get('qualifier'))
        if q is None:
            reason = 'qualifier source not found'
        elif design.signals[q]['component_id'] != s['component_id']:
            reason = 'qualifier and data are in different components'
        else:
            ports['qualifier'] = design.signals[q]['name']
    if not module:
        reason = 'component has no Verilog module name'
    elif not clock:
        reason = 'clock is not visible in the component'
    if reason:
        return dict(bind=None, unbound_reason=reason)
    return dict(bind=dict(module=module, instance=comp.get('path'), ports=ports))
