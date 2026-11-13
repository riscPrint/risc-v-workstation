"""VHDL source locations for GHDL netlists, from the GHDL XML AST (`ghdl --file-to-xml`).

The GHDL Yosys plugin writes no `src` attributes. The AST gives the entity, port, signal,
instance and assignment lines; they are applied after the netlist import."""
from __future__ import annotations

import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ASSIGN = re.compile(r'.*signal_assignment.*')


def plugin_path(tool, explicit):
    """The GHDL plugin: --ghdl-plugin PATH, $RVW_GHDL_PLUGIN, or the plugin bundled with Yosys."""
    selected = explicit or os.environ.get('RVW_GHDL_PLUGIN')
    if selected:
        return Path(selected).absolute()
    bundled = Path(tool.resolved).parents[1] / 'share' / 'yosys' / 'plugins' / 'ghdl.so'
    if not bundled.is_file():
        raise ValueError('ghdl frontend needs the GHDL Yosys plugin: set RVW_GHDL_PLUGIN, pass '
                         '--ghdl-plugin, or run scripts/build-ghdl-plugin.py')
    return bundled


def ghdl_prefix(tool):
    """GHDL_PREFIX for libghdl inside Yosys: the environment, else OSS CAD Suite's lib/ghdl."""
    if os.environ.get('GHDL_PREFIX'):
        return os.environ['GHDL_PREFIX']
    candidate = Path(tool.resolved).parents[1] / 'lib' / 'ghdl'
    return str(candidate) if candidate.is_dir() else None


def locations(xml_text: str) -> dict:
    """{'entities': {e: (file, line)}, 'decls': {(e, id): (file, line)},
    'assigns': {(e, id): [(file, line)]}, 'instances': {(e, label): (file, line)}}.
    Identifiers are lower case, as GHDL prints them."""
    root = ET.fromstring(xml_text)
    out = {'entities': {}, 'decls': {}, 'assigns': {}, 'instances': {}}

    def where(el):
        return el.get('file'), int(el.get('line', '0') or 0)

    def target_name(el):
        target = el.find('target')
        if target is None:
            return None
        for t in target.iter():
            if t.get('kind') == 'simple_name' and t.get('identifier'):
                return t.get('identifier').lower()
        return None

    def walk(el, entity):
        kind = el.get('kind', '')
        if kind == 'entity_declaration':
            entity = el.get('identifier', '').lower()
            out['entities'][entity] = where(el)
        elif kind == 'architecture_body':
            name = el.find('entity_name')
            entity = (name.get('identifier') or '').lower() if name is not None else entity
        elif entity and kind in ('interface_signal_declaration', 'signal_declaration'):
            out['decls'].setdefault((entity, el.get('identifier', '').lower()), where(el))
        elif entity and kind == 'component_instantiation_statement':
            out['instances'].setdefault((entity, el.get('label', '').lower()), where(el))
        elif entity and ASSIGN.fullmatch(kind):
            name = target_name(el)
            if name:
                out['assigns'].setdefault((entity, name), []).append(where(el))
        for child in el:
            walk(child, entity)

    walk(root, None)
    return out


def entity_of(module: str, entities) -> str | None:
    """GHDL names a specialized architecture `<entity>_B<arch>[_L<lib>][_<generics or hash>]`."""
    low = module.lower()
    if low in entities:
        return low
    best = [e for e in entities if low.startswith(e + '_b')]
    return max(best, key=len) if best else None


def apply(conn, locs: dict, paths: dict) -> None:
    """Fill locations of components, signals and net-alias assignments that have none."""
    files = {p: i for i, p in conn.execute('SELECT id, path FROM files')}

    def fid(copy):
        source = paths.get(os.path.realpath(copy)) if copy else None
        if source is None:
            return None
        if source not in files:
            files[source] = len(files) + 1 + max(files.values(), default=0)
            conn.execute('INSERT INTO files VALUES (?,?)', (files[source], source))
        return files[source]

    entities = locs['entities']
    comps = list(conn.execute('SELECT id, module, name, parent_id FROM components'))
    for cid, module, name, parent in comps:
        entity = module.lower() if module else None
        if entity in entities:
            f, line = entities[entity]
            conn.execute('UPDATE components SET file_id=?, line=? WHERE id=? AND file_id IS NULL',
                         (fid(f), line, cid))
        for sid, sname in conn.execute('SELECT id, name FROM signals WHERE component_id=? AND generated=0', (cid,)).fetchall():
            base = re.sub(r'\[.*$', '', sname).lower()
            if (entity, base) in locs['decls']:
                f, line = locs['decls'][(entity, base)]
                conn.execute('UPDATE signals SET file_id=?, line=? WHERE id=? AND file_id IS NULL', (fid(f), line, sid))
            for f, line in locs['assigns'].get((entity, base), [])[:1]:
                conn.execute("UPDATE assignments SET file_id=?, line=? WHERE target_id=? AND file_id IS NULL", (fid(f), line, sid))
