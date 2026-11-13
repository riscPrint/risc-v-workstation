"""RTL lint rules on the design database. Each rule has a default severity; settings can
change it or turn it off. Results are findings or inconclusive, never signoff."""
import re
import sqlite3

from .graph import Design


RULES = {
    'lint.comb_loop': ('error', 'Combinational loop.'),
    'lint.multiple_drivers': ('error', 'Signal is assigned from more than one component.'),
    'lint.input_driven': ('error', 'A toplevel input is assigned inside the design.'),
    'lint.latch': ('error', 'Combinational signal is assigned only under conditions. It infers a latch.'),
    'lint.width_truncation': ('warning', 'Resize drops upper bits.'),
    'lint.width_extension': ('info', 'Resize extends a value.'),
    'lint.unused': ('info', 'Signal has no loads.'),
    'lint.undriven': ('error', 'Signal has no driver.'),
    'lint.constant_register': ('info', 'Register is never assigned after reset.'),
    'lint.fsm_unreachable': ('warning', 'Enumerated state is never assigned to the state register.'),
    'lint.no_reset': ('info', 'Register has no reset in a clock domain with a reset.'),
    'lint.clock_as_data': ('error', 'A clock net reaches register data or control logic.'),
    'lint.unconnected_output': ('warning', 'Output port of a child component has no loads.'),
    'lint.naming': ('warning', 'Name breaks the naming rule.'),
    'lint.max_fanout': ('warning', 'Signal fan-out exceeds the limit.'),
}
SEVERITIES = {'off', 'info', 'warning', 'error'}
KEYWORDS = set('''always and assign automatic begin buf bufif0 bufif1 case casex casez cell cmos config deassign
default defparam design disable edge else end endcase endconfig endfunction endgenerate endmodule endprimitive
endspecify endtable endtask event for force forever fork function generate genvar highz0 highz1 if ifnone
incdir include initial inout input instance integer join large liblist library localparam macromodule medium
module nand negedge nmos nor noshowcancelled not notif0 notif1 or output parameter pmos posedge primitive pull0
pull1 pulldown pullup pulsestyle_onevent pulsestyle_ondetect rcmos real realtime reg release repeat rnmos rpmos
rtran rtranif0 rtranif1 scalared showcancelled signed small specify specparam strong0 strong1 supply0 supply1
table task time tran tranif0 tranif1 tri tri0 tri1 triand trior trireg unsigned use uwire vectored wait wand
weak0 weak1 while wire wor xnor xor logic bit byte int shortint longint interface class package program
property sequence assert assume cover type typedef enum struct union string void'''.split())
RESIZE = re.compile(r'Resize\w*<(\d+)>\[\d+\]\(([^\[\(,]*?)\[(\d+)\]')
ENUM_LIT = re.compile(r'\.([A-Za-z_]\w*)#\d+')


def settings(cfg):
    """Normalize the `rules` settings block: {rule: severity | {severity, ...params}}."""
    if cfg is None:
        cfg = {}
    if not isinstance(cfg, dict):
        raise ValueError('rules must be an object of rule settings')
    out = {}
    for rule, value in cfg.items():
        if rule not in RULES:
            raise ValueError(f'unknown lint rule: {rule}')
        if isinstance(value, str):
            value = {'severity': value}
        if not isinstance(value, dict) or value.get('severity', RULES[rule][0]) not in SEVERITIES:
            raise ValueError(f'{rule} needs severity off, info, warning or error')
        out[rule] = value
    for key in ('ports', 'registers', 'signals'):
        pattern = out.get('lint.naming', {}).get(key)
        if pattern is not None:
            try:
                re.compile(pattern)
            except (re.error, TypeError) as exc:
                raise ValueError(f'lint.naming {key} is not a regular expression: {exc}') from exc
    limit = out.get('lint.max_fanout', {}).get('limit', 512)
    if type(limit) is not int or limit < 1:
        raise ValueError('lint.max_fanout limit must be a positive integer')
    return out


def sccs(nodes, succ):
    """Strongly connected components (iterative Tarjan)."""
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(succ(root)))]
        index[root] = low[root] = counter[0]; counter[0] += 1
        stack.append(root); on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(succ(w))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                out.append(comp)
    return out


def complete_assignment(assigns, conditions, width):
    """Reduce full-width assignments through exhaustive source condition branches."""
    if not isinstance(width, int) or width < 1:
        return False
    covered = {}
    for a in assigns:
        match = re.fullmatch(r'\((\d+)(?: downto (\d+))?\)', a['range'] or '')
        bits = set(range(width)) if a['range'] is None else set(
            range(int(match[2] or match[1]), int(match[1]) + 1)) if match else set()
        covered.setdefault(a['cond_id'], set()).update(bits)

    changed = True
    while changed and len(covered.get(None, ())) < width:
        changed = False
        for i in list(covered):
            c = conditions.get(i)
            if not c:
                continue
            siblings = [x for x in conditions.values() if
                        (x['parent_id'], x['component_id'], x['file_id'], x['line'], x['signal_id']) ==
                        (c['parent_id'], c['component_id'], c['file_id'], c['line'], c['signal_id'])]
            if c['kind'] in ('when', 'else'):
                siblings = [x for x in siblings if x['kind'] in ('when', 'else') and x['key'] == c['key']]
                exhaustive = {x['kind'] for x in siblings} == {'when', 'else'}
            else:
                siblings = [x for x in siblings if x['kind'] in ('case', 'default')]
                exhaustive = any(x['kind'] == 'default' for x in siblings)
            if exhaustive and all(x['id'] in covered for x in siblings):
                common = set.intersection(*(covered[x['id']] for x in siblings))
                parent = covered.setdefault(c['parent_id'], set())
                if not common <= parent:
                    parent.update(common)
                    changed = True
    return len(covered.get(None, ())) == width


def analyze(db, config=None):
    conf = settings(config)
    design = Design(db.conn)
    d, findings = design, []
    unresolved = []

    def severity(rule):
        return conf.get(rule, {}).get('severity', RULES[rule][0])

    def emit(rule, i, message=None, **extra):
        sev = severity(rule)
        if sev == 'off':
            return None
        s = d.signals[i]
        findings.append(dict(rule=rule, severity=sev, endpoint=s['path'], file=s['file'], line=s['line'],
                             message=message or RULES[rule][1], **extra))
        return findings[-1]

    live = {i: s for i, s in d.signals.items() if not s['pruned']}
    comb = {i for i, s in live.items() if s['kind'] == 'wire'}
    clock_nets = {i for i, s in live.items() if s.get('clock_role') == 'clock'} | {
        d.by_path[x['clock']] for x in d.domains.values() if x.get('clock') in d.by_path}
    role = {i for i, s in live.items() if s.get('clock_role')}

    # Combinational loops: cycles through wires only.
    for comp in sccs(sorted(comb), lambda v: [w for w in d.outgoing[v] if w in comb and
                                               (v, w) not in d.alias_edges and d.kinds[(v, w)] - {'blackbox'}]):
        if len(comp) > 1 or comp[0] in d.outgoing[comp[0]]:
            names = {i for i in comp if not d.signals[i].get('generated')}
            names |= {o for i in comp for o in d.owners.get(i, ())}
            members = sorted({d.signals[i]['path'] for i in names} or {d.signals[i]['path'] for i in comp})
            emit('lint.comb_loop', d.by_path[members[0]], f'Combinational loop through {len(comp)} signal(s).',
                 members=members[:50])

    # HDL imports record net aliases as assignments; they drive nothing.
    # A constant net's alias row has no reads: it is a tie, so it stays a driver.
    read = {r[0] for r in db.conn.execute('SELECT DISTINCT assignment_id FROM assign_reads')}
    rows = [a for a in db.conn.execute('SELECT * FROM assignments')
            if a['source'] != 'Yosys net alias' or a['id'] not in read]
    conditions = {r['id']: dict(r) for r in db.conn.execute('SELECT * FROM conds')}
    by_target = {}
    for a in rows:
        by_target.setdefault(a['target_id'], []).append(a)
    for t, assigns in sorted(by_target.items()):
        if t not in live:
            continue
        s = live[t]
        data = [a for a in assigns if a['kind'] == 'data']
        if any(a['source'] in ('$dlatch', '$adlatch') for a in data):
            emit('lint.latch', t, 'Lowered HDL contains a level-sensitive latch.')
        comps = {a['component_id'] for a in data}
        if len(comps) > 1:
            emit('lint.multiple_drivers', t, components=sorted(
                (d.components.get(c) or {}).get('path', '?') for c in comps))
        if data and d.is_top_input(t):
            emit('lint.input_driven', t)
        if s['kind'] == 'wire' and data and all(a['cond_id'] is not None for a in data) and t not in role and not complete_assignment(data, conditions, s['width']):
            if 'spinaldb:conditionalDeclaration' in (s.get('tags') or '') or (s.get('generated') and len(data) == 1 and data[0]['range'] is None):
                # Spinal can hoist generated expression temporaries out of their
                # source scope. A condition in this database is not a lowered
                # RTL enable, so it cannot establish latch inference.
                unresolved.append(dict(rule='lint.latch', endpoint=s['path'],
                    reason='Expression has source-scope condition evidence; inspect lowered RTL.'))
            else:
                emit('lint.latch', t)
        for a in data:
            for m in RESIZE.finditer(a['key'] or ''):
                target, source = int(m.group(1)), int(m.group(3))
                if source > target:
                    emit('lint.width_truncation', t, f'Resize from {source} to {target} bits drops upper bits.',
                         source_width=source, target_width=target)
                elif source < target:
                    emit('lint.width_extension', t, f'Resize from {source} to {target} bits.',
                         source_width=source, target_width=target)

    def linked(i):
        return {b for b in d.outgoing[i] | d.incoming[i] if (i, b) in d.alias_edges}

    def driven(i):
        # Through alias bits: a real driver, a tie or constant, or a toplevel input sharing the bit.
        return bool(d.drivers(i)) or any(by_target.get(b) or any(d.is_top_input(o) for o in d.owners.get(b, ()))
                                         for b in linked(i))

    def loaded(i):
        return bool(d.loads(i)) or any(any(d.is_top_output(o) for o in d.owners.get(b, ())) for b in linked(i))

    for i, s in sorted(live.items()):
        if s['kind'] not in ('wire', 'reg') or s.get('generated'):
            continue
        comp = d.components.get(s['component_id'], {})
        boxed = bool(comp.get('blackbox'))
        tied = any(a['id'] not in read and a['source'] and a['source'].startswith('Yosys')
                   for a in by_target.get(i, []))  # HDL constant net: used as a value
        if not loaded(i) and not d.is_top_output(i) and i not in role and not boxed and not tied:
            if s['direction'] == 'out' and comp.get('depth', 0) > 0:
                emit('lint.unconnected_output', i)
            elif s['direction'] is None:
                emit('lint.unused', i)
        if (not by_target.get(i) and not driven(i) and not d.is_top_input(i) and i not in role
                and not (boxed and s['direction'] == 'out') and s['kind'] == 'wire'):
            emit('lint.undriven', i)
        if s['kind'] == 'reg' and not d.incoming[i] and not any(
                a['kind'] == 'data' for a in by_target.get(i, [])):
            emit('lint.constant_register', i)
        if s['kind'] == 'reg' and s['reset_value'] is None:
            dom = d.domains.get(s['clock_domain_id']) or {}
            if dom.get('reset') or dom.get('soft_reset'):
                emit('lint.no_reset', i)
        limit = conf.get('lint.max_fanout', {}).get('limit', 512)
        fanout = len(d.loads(i))
        if fanout > limit and i not in role:
            emit('lint.max_fanout', i, f'Fan-out {fanout} exceeds {limit}.', fanout=fanout)
        naming = conf.get('lint.naming', {})
        group = 'ports' if s['direction'] else ('registers' if s['kind'] == 'reg' else 'signals')
        pattern = naming.get(group)
        if s['name'] in KEYWORDS:
            emit('lint.naming', i, f"Name {s['name']} is a Verilog or SystemVerilog keyword.")
        elif pattern and not re.fullmatch(pattern, s['name']):
            emit('lint.naming', i, f"Name {s['name']} does not match the {group} pattern {pattern}.")

    for i in sorted(clock_nets):
        found, _ = d.fanout(i, stop=lambda n: n in clock_nets)
        for r in sorted(n for n in found if n in d.regs and n != i):
            emit('lint.clock_as_data', r, f"Clock {d.signals[i]['path']} reaches this register's logic.",
                 clock=d.signals[i]['path'])

    fsm = fsm_states(d, by_target)
    for row in fsm:
        if row['status'] == 'inconclusive':
            unresolved.append(dict(rule='lint.fsm_unreachable', endpoint=row['register'], reason=row['reason']))
        if row['status'] == 'checked':
            for state in row['unreachable']:
                emit('lint.fsm_unreachable', d.by_path[row['register']],
                     f"State {state} is never assigned to {row['register']}.", state=state)
    return dict(status='inconclusive' if d.blackbox_edges or unresolved else 'completed', findings=findings,
                unresolved=unresolved,
                rules=[dict(id=r, severity=severity(r)) for r in sorted(RULES)], fsm=fsm,
                scope='design-database lint rules; no simulation or synthesis')


def fsm_states(d, by_target):
    """States assigned to each enum register through its same-type combinational cone."""
    out = []
    for i, s in sorted(d.regs.items()):
        m = re.fullmatch(r'[^@]+@\w+\[\d+\]\{(.*)\}', s['type'] or '')
        if not m:
            continue
        states = [x.split('=')[0] for x in m.group(1).split(',') if x]
        internal, _ = d.cone(i)
        group = {i} | {n for n in internal if d.signals[n]['type'] == s['type']}
        names, closed = set(), True
        for n in group:
            for a in by_target.get(n, []):
                key = a['key'] or ''
                lits = ENUM_LIT.findall(key)
                # Readable source retains exact literals when a long typed key is hashed.
                enum_name = s['type'].split('@', 1)[0]
                if not lits and a['source'] in {enum_name + '.' + state for state in states}:
                    lits = [a['source'].rsplit('.', 1)[-1]]
                names.update(lits)
                reads = {r[0] for r in d.c.execute('SELECT signal_id FROM assign_reads WHERE assignment_id=?', (a['id'],))}
                if not lits and (not reads or not reads <= group):
                    closed = False
        if s['reset_value']:
            names.update(re.findall(r'[A-Za-z_]\w*', s['reset_value']))
        if not closed:
            out.append(dict(register=s['path'], states=states, status='inconclusive',
                            reason='a state source is not an enum literal or the state logic'))
            continue
        out.append(dict(register=s['path'], states=states, status='checked',
                        unreachable=[x for x in states if x not in names]))
    return out


def run(path, config):
    from rvw.query.db import run_on
    try:
        return run_on(path, lambda db: analyze(db, config))
    except sqlite3.DatabaseError as exc:
        return dict(status='inconclusive', findings=[], error=str(exc))
