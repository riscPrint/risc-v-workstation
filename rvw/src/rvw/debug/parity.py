"""Compare debug artifacts with explicit, audited caller-location equivalence.

No source fields are dropped. A caller mapping represents a changed elaboration
entry point, not a claim that the source files or lines are identical.
"""
from __future__ import annotations

from collections import Counter
import copy
import json
from pathlib import Path


def normalize(value, *, roots=(), callers=()):
    value = copy.deepcopy(value)
    def walk(node):
        if isinstance(node, list):
            return [walk(v) for v in node]
        if not isinstance(node, dict):
            return node
        node = {k: walk(v) for k, v in node.items()}
        if isinstance(node.get('file'), str):
            path = Path(node['file'])
            if path.is_absolute():
                matches = [path.relative_to(Path(r)).as_posix() for r in roots if path.is_relative_to(Path(r))]
                if matches:
                    node['file'] = min(matches, key=len)
            for old_file, old_line, new_file, new_line in callers:
                if node['file'] == old_file and node.get('line') == old_line:
                    node['file'], node['line'] = new_file, new_line
                    break
        # Spinal can also use the caller location in a generated node identifier.
        for key in ('id', 'name'):
            if isinstance(node.get(key), str):
                for a, line_a, b, line_b in callers:
                    if node[key] == f'{a}:{line_a}':
                        node[key] = f'{b}:{line_b}'
                    old = f'{Path(a).stem}_l{line_a}'
                    new = f'{Path(b).stem}_l{line_b}'
                    if node[key] in (old, 'sig:' + old):
                        node[key] = node[key].replace(old, new)
        return node
    return walk(value)


def graph_key(graph):
    """Retain every vertex field, edge field and duplicate edge."""
    if not graph['vertices'] or not graph['edges']:
        raise ValueError('empty graph is not parity evidence')
    dump = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'))
    vertices = [dump(v) for v in graph['vertices']]
    edges = []
    for edge in graph['edges']:
        edge = dict(edge)
        edge['from'], edge['to'] = vertices[edge['from']], vertices[edge['to']]
        edges.append(dump(edge))
    metadata = {k: v for k, v in graph.items() if k not in ('vertices', 'edges')}
    return metadata, Counter(vertices), Counter(edges)


def compare(left, right, *, kind, left_roots=(), right_roots=(), callers=()):
    a = normalize(left, roots=left_roots, callers=callers)
    b = normalize(right, roots=right_roots)
    if kind == 'blocks':
        # The extraction time is not design/source-navigation information.
        a.pop('generated', None)
        b.pop('generated', None)
        return a == b
    if kind == 'trace':
        return graph_key(a) == graph_key(b)
    raise ValueError('kind must be blocks or trace')
