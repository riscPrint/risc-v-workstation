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
        self._assign = None

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
