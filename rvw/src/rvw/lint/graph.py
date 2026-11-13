"""Shared read-only view of a SpinalDB design for the lint, CDC, RDC and SDC checks."""
from collections import defaultdict
import sqlite3


RESET_FIELDS = ('reset_key', 'reset_kind', 'reset_active_high', 'soft_reset_key', 'soft_reset_active_high')


class Design:
    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self.c = conn
        self.tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.domains = {r['id']: dict(r) for r in conn.execute('SELECT * FROM clock_domains')}
        self.components = {r['id']: dict(r) for r in conn.execute('SELECT * FROM components')}
        self.signals = {r['id']: dict(r) for r in conn.execute(
            'SELECT s.*, f.path AS file FROM signals s LEFT JOIN files f ON f.id=s.file_id')}
        self.regs = {i: s for i, s in self.signals.items() if s['kind'] == 'reg' and not s['pruned']}
        self.by_path = {}
        for i, s in self.signals.items():
            self.by_path.setdefault(s['path'], i)
        self.incoming, self.outgoing = defaultdict(set), defaultdict(set)
        self.kinds = defaultdict(set)
        self.blackbox_edges = False
        for src, dst, kind in conn.execute('SELECT src,dst,kind FROM edges'):
            if kind == 'init':
                continue
            self.blackbox_edges |= kind == 'blackbox'
            self.incoming[dst].add(src)
            self.outgoing[src].add(dst)
            self.kinds[(src, dst)].add(kind)
        meta = dict(conn.execute('SELECT key, value FROM meta')) if 'meta' in self.tables else {}
        self.frontend = meta.get('frontend')
        if (self.frontend or '').startswith('yosys-'):
            self._merge_hdl_aliases()
        self.members = getattr(self, 'members', {})
        self.alias_edges = getattr(self, 'alias_edges', set())
        self.owners = getattr(self, 'owners', {})
        self._assign = None

    def _merge_hdl_aliases(self):
        """HDL imports link each named net to its bit nodes in both directions (`Yosys net alias`
        rows). Drop the links of hidden names, merge the bits of a register vector into its one
        visible name, and keep other links as connectivity that the loop check ignores."""
        sig = self.signals
        links = {(t, b) for t, b in self.c.execute(
            "SELECT a.target_id, r.signal_id FROM assignments a JOIN assign_reads r ON r.assignment_id=a.id "
            "WHERE a.source='Yosys net alias'") if t != b}
        owners = {}
        for t, b in links:
            if not sig[t].get('generated'):
                owners.setdefault(b, set()).add(t)
        members = {}
        for b, vs in owners.items():
            for v in vs:
                members.setdefault(v, set()).add(b)
        rep = {}
        # Only register vectors merge: a merged wire vector would join its bit slices into false loops.
        for v, bits in members.items():
            if sig[v]['kind'] == 'reg' and all(owners[b] == {v} for b in bits):
                for b in bits:
                    rep[b] = v
        drop = {p for t, b in links if sig[t].get('generated') or rep.get(b) == t for p in ((t, b), (b, t))}
        self.members = {v: bits for v, bits in members.items() if all(rep.get(b) == v for b in bits)}
        old = self.kinds
        self.incoming, self.outgoing, self.kinds = defaultdict(set), defaultdict(set), defaultdict(set)
        for (a, b), ks in old.items():
            if (a, b) in drop:
                continue
            x, y = rep.get(a, a), rep.get(b, b)
            if x == y and a != b:
                continue
            self.incoming[y].add(x)
            self.outgoing[x].add(y)
            self.kinds[(x, y)] |= ks
        self.alias_edges = {p for t, b in links for p in ((t, b), (b, t)) if p not in drop}
        self.owners = owners
        for b in rep:
            self.regs.pop(b, None)

    # Structure -----------------------------------------------------------------
    def is_top_input(self, i):
        s = self.signals[i]
        comp = self.components.get(s['component_id'], {})
        return s['direction'] == 'in' and comp.get('depth', 0) == 0

    def is_top_output(self, i):
        s = self.signals[i]
        comp = self.components.get(s['component_id'], {})
        return s['direction'] == 'out' and comp.get('depth', 0) == 0

    def cone(self, node):
        """Combinational fan-in of a node: (internal nodes, leaves). Leaves are registers,
        memories and nodes without inputs. The node itself is not a leaf."""
        pending, seen, leaves = list(self.incoming[node]), set(), set()
        while pending:
            n = pending.pop()
            if n in seen:
                continue
            seen.add(n)
            if n in self.regs or self.signals.get(n, {}).get('kind') in ('mem', 'mem_read') or not self.incoming[n]:
                leaves.add(n)
            else:
                pending.extend(self.incoming[n])
        return seen - leaves, leaves

    def loads(self, i):
        """Real (non-alias) loads of a net, also through the bits it names."""
        out = {w for w in self.outgoing[i] if (i, w) not in self.alias_edges}
        for b in self.outgoing[i]:
            if (i, b) in self.alias_edges:
                out |= {w for w in self.outgoing[b] if (b, w) not in self.alias_edges}
        return out

    def drivers(self, i):
        out = {w for w in self.incoming[i] if (w, i) not in self.alias_edges}
        for b in self.incoming[i]:
            if (b, i) in self.alias_edges:
                out |= {w for w in self.incoming[b] if (w, b) not in self.alias_edges}
        return out

    def upstream_regs(self, node):
        return {n for n in self.cone(node)[1] if n in self.regs}

    def fanout(self, node, stop=None):
        """Combinational fan-out of a node: registers and other stops reached through wires."""
        pending, seen, found = list(self.outgoing[node]), set(), set()
        while pending:
            n = pending.pop()
            if n in seen:
                continue
            seen.add(n)
            if n in self.regs or (stop and stop(n)):
                found.add(n)
            else:
                pending.extend(self.outgoing[n])
        return found, seen

    def domain(self, i):
        s = self.signals.get(i) or {}
        return self.domains.get(s.get('clock_domain_id'))

    def clock(self, i):
        d = self.domain(i) or {}
        return d.get('clock_key'), d.get('clock_edge')

    def assignments(self, target):
        if self._assign is None:
            self._assign = defaultdict(list)
            for r in self.c.execute("SELECT * FROM assignments ORDER BY seq"):
                self._assign[r['target_id']].append(dict(r))
        return self._assign.get(target, [])

    def component_path(self, i):
        comp = self.components.get(self.signals[i]['component_id'])
        return comp['path'] if comp else None

    def component_classes(self, i):
        """Class names from the signal's own component up to the toplevel."""
        out, comp = [], self.components.get(self.signals[i]['component_id'])
        while comp:
            out.append((comp['path'], comp.get('class_name') or ''))
            comp = self.components.get(comp['parent_id'])
        return out

    def ref(self, i):
        s = self.signals[i]
        return dict(path=s['path'], file=s['file'], line=s['line'])
