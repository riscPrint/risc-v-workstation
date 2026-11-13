"""Chisel through FIRRTL: firtool emits Verilog and HGLDD; locations map back to Scala lines.

firtool writes `// File.scala:12:7, :15:3` after each emitted Verilog line (plain location
style). Every database location that points at an emitted Verilog line is rebound to the Scala
location of that line when the Scala file is captured under the source root. The Verilog stays
in the database (artifacts `rtl/*`), with the line map (`hdl/source-map.json`) and HGLDD
(`hgldd/*.dd`, for `rvw query export hgldd`)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

COMMENT = re.compile(r'//\s*(.*)$')
LOC = re.compile(r'^(?:(?P<file>[^\s,:][^,]*?\.scala))?:(?P<line>\d+):\d+$')
FIRTOOL_OPTIONS = ['-g', '--emit-hgldd', '--disable-all-randomization',
                   '--lowering-options=disallowLocalVariables,disallowPackedArrays,locationInfoStyle=plain']


def firtool_argv(tool, fir, outdir):
    return [str(tool), str(fir), '--split-verilog', '-o', str(outdir), f'--hgldd-output-dir={outdir}',
            *FIRTOOL_OPTIONS]


def emitted(outdir: Path) -> list[Path]:
    """Verilog files in firtool's file list order (dependencies first)."""
    listing = outdir / 'filelist.f'
    names = [l.strip() for l in listing.read_text().splitlines() if l.strip()] if listing.exists() else []
    files = [outdir / n for n in names] or sorted(outdir.glob('*.sv')) + sorted(outdir.glob('*.v'))
    return [f for f in files if f.suffix in ('.sv', '.v')]


def line_map(text: str) -> dict[int, list[tuple[str, int]]]:
    """{verilog line: [(scala file, line), ...]} from firtool's trailing location comments."""
    out = {}
    for number, line in enumerate(text.splitlines(), 1):
        m = COMMENT.search(line)
        if not m:
            continue
        locs, last = [], None
        for part in (p.strip() for p in m[1].split(',')):
            lm = LOC.match(part)
            if not lm:
                locs = []
                break
            last = lm['file'] or last
            if last is None:
                locs = []
                break
            locs.append((last, int(lm['line'])))
        if locs:
            out[number] = locs
    return out


def chisel_names(hgldd: dict) -> dict[str, dict[str, str]]:
    """{module: {verilog signal: Chisel path}} from HGLDD module port_vars (first claim wins,
    firtool temporaries `_*` are skipped)."""
    objects = hgldd.get('objects', [])
    structs = {o['obj_name']: o for o in objects if o.get('kind') == 'struct'}
    out = {}
    for module in (o for o in objects if o.get('kind') == 'module'):
        names = out.setdefault(module.get('module_name') or module['obj_name'], {})

        def walk(path, value, var):
            if not isinstance(value, dict):
                return
            if 'sig_name' in value:
                sig = value['sig_name']
                if not sig.startswith('_') and sig not in names:
                    names[sig] = path
                return
            if value.get('opcode') != "'{":
                return
            ops = value.get('operands', [])
            struct = structs.get(var.get('type_name'))
            if struct and not var.get('unpacked_range'):
                for field, op in zip(struct.get('port_vars', []), ops):
                    walk(f"{path}.{field['var_name']}", op, field)
            elif var.get('unpacked_range'):
                element = {k: v for k, v in var.items() if k != 'unpacked_range'}
                for i, op in enumerate(ops):
                    walk(f'{path}.{i}', op, element)

        for var in module.get('port_vars', []):
            walk(var['var_name'], var.get('value'), var)
    return out


def apply(conn, rtl: dict, scala_files: dict, hgldd: dict) -> int:
    """Rebind locations in emitted Verilog to Scala. `rtl` maps the database name of each
    emitted file (`rtl/Top.sv`) to its text; `scala_files` maps a Scala path as firtool prints it
    to its captured source path. Declarations take the first location of their line,
    assignments the last. Returns the number of rebound rows."""
    maps = {name: line_map(text) for name, text in rtl.items()}
    files = {p: i for i, p in conn.execute('SELECT id, path FROM files')}

    def fid(path):
        if path not in files:
            files[path] = max(files.values(), default=0) + 1
            conn.execute('INSERT INTO files VALUES (?,?)', (files[path], path))
        return files[path]

    names = {i: p for p, i in files.items()}
    count = 0
    for table, pick in (('signals', 0), ('components', 0), ('assignments', -1), ('memories', 0), ('mem_ports', 0)):
        for rid, file_id, line in conn.execute(f'SELECT id, file_id, line FROM {table} WHERE file_id IS NOT NULL').fetchall():
            locs = maps.get(names.get(file_id), {}).get(line)
            bound = [(scala_files[f], l) for f, l in locs or [] if f in scala_files]
            if bound:
                path, l = bound[pick]
                conn.execute(f'UPDATE {table} SET file_id=?, line=? WHERE id=?', (fid(path), l, rid))
                count += 1
    # Emitted Verilog is an artifact, not a captured source: clear locations left on it.
    for name in rtl:
        if name in files:
            for table in ('signals', 'components', 'assignments', 'memories', 'mem_ports'):
                conn.execute(f'UPDATE {table} SET file_id=NULL, line=NULL WHERE file_id=?', (files[name],))
            conn.execute('DELETE FROM files WHERE id=?', (files[name],))
    # Chisel names as the second spelling of each signal (queried like Spinal paths).
    comps = dict(conn.execute('SELECT id, module FROM components'))
    paths = dict(conn.execute('SELECT id, path FROM components'))
    for sid, cid, name in conn.execute('SELECT id, component_id, name FROM signals WHERE generated=0').fetchall():
        chisel = hgldd.get(comps.get(cid), {}).get(name)
        if chisel and chisel != name:
            prefix = (paths[cid] + '.') if paths[cid] else ''
            conn.execute('UPDATE signals SET spinal_path=? WHERE id=?', (prefix + chisel, sid))
    return count


def scala_paths(rtl_texts) -> set[str]:
    return {f for text in rtl_texts for locs in line_map(text).values() for f, _ in locs}


def resolve_scala(rel: str, roots) -> Path | None:
    for root in roots:
        candidate = Path(rel) if os.path.isabs(rel) else Path(root) / rel
        if candidate.is_file():
            return candidate
    return None


def load_hgldd(outdir: Path) -> tuple[dict, dict]:
    """({module: {signal: Chisel path}}, {artifact name: bytes})."""
    names, artifacts = {}, {}
    for dd in sorted(outdir.glob('*.dd')):
        data = dd.read_bytes()
        artifacts[f'hgldd/{dd.name}'] = data
        for module, mapping in chisel_names(json.loads(data)).items():
            names.setdefault(module, {}).update(mapping)
    return names, artifacts
