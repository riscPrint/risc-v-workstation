"""Conservative C6 navigation from the native Yosys Verilog/SV subset."""
from __future__ import annotations

from importlib.resources import files
import gzip
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from rvw.common.capture import Capture
from rvw.common.proc import run_group

# Each supported cell has only ordinary value input and output ports.
COMB = set(('not pos neg and or xor xnor reduce_and reduce_or reduce_xor reduce_xnor '
            'reduce_bool logic_not logic_and logic_or shl shr sshl sshr shift shiftx '
            'lt le eq ne eqx nex ge gt add sub mul div mod divfloor modfloor pow '
            'mux pmux bmux demux slice concat alu fa lcu buf').split())
STATE = {'dff', 'adff', 'sdff', 'dffe', 'adffe', 'sdffe', 'sdffce', 'dlatch', 'adlatch', 'aldff', 'aldffe'}
MEMORY = {'memrd', 'memrd_v2', 'memwr', 'memwr_v2', 'meminit', 'meminit_v2'}


def schema_sql():
    return files('rvw.query').joinpath('schema.sql').read_text()


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


FRONTENDS = {'yosys': 'yosys-verilog', 'slang': 'yosys-slang', 'ghdl': 'yosys-ghdl', 'chisel': 'yosys-firtool'}
def strip_comments(text):
    """Remove HDL comments while retaining strings and line numbers."""
    pattern = r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else
                  ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)


SOURCE_REMAP = r'\$(?:readmem\w*|fopen)\b|`line\b|``'


def _slang_plugin(tool, plugin):
    """The yosys-slang plugin: --slang PATH, $RVW_SLANG, or the plugin bundled with Yosys."""
    plugin = plugin or os.environ.get('RVW_SLANG')
    if plugin:
        return Path(plugin).absolute()
    bundled = Path(tool.resolved).parents[1] / 'share' / 'yosys' / 'plugins' / 'slang.so'
    if not bundled.is_file():
        raise ValueError('slang frontend needs the yosys-slang plugin: set RVW_SLANG, pass --slang, '
                         'or run scripts/install.sh --with-formal')
    return bundled


def build_hdl(sources, top, out, *, cache_dir=None, **options):
    """Build normally, or reuse a whole-design source-hash cache when requested."""
    sources = list(sources)
    if not sources or Path(out).resolve() in {Path(p).resolve() for p in sources}:
        raise ValueError('supply sources; output must not alias an input')
    if cache_dir is not None:
        from .build_cache import cached_build
        return cached_build(_build_hdl, sources, top, out, cache_dir, options)
    return _build_hdl(sources, top, out, **options)


def _build_hdl(sources, top, out, *, yosys='yosys', timeout=120, frontend='yosys', include_dirs=(),
              defines=(), parameters=(), std=None, slang=None, ghdl_plugin=None, library='work',
              firtool=None, source_roots=()):
    """Capture, elaborate, translate and atomically publish. Errors keep old output.

    `frontend` is `yosys` (native read_verilog -sv subset, self-contained files), `slang`
    (yosys-slang: full SystemVerilog with include directories, defines and top parameters) or
    `ghdl` (VHDL through the GHDL Yosys plugin; `parameters` are top generics, `std` 93/08) or
    `chisel` (FIRRTL files through firtool, then the native reader; `source_roots` hold the
    Scala sources that firtool's locations name)."""
    if frontend not in FRONTENDS:
        raise ValueError(f'unknown frontend {frontend!r}')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9$]*', top):
        raise ValueError('unsupported top module name')
    for value in (*defines, *parameters):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(=[^\s"\\]*)?', value):
            raise ValueError(f'unsupported define or parameter: {value!r}')
    if frontend == 'yosys' and (include_dirs or defines or parameters or std):
        raise ValueError('include directories, defines, parameters and --std need --frontend slang')
    if frontend == 'chisel' and (include_dirs or defines or parameters or std):
        raise ValueError('a FIRRTL circuit is elaborated: no include directories, defines, parameters or --std')
    if frontend == 'ghdl' and (include_dirs or defines):
        raise ValueError('VHDL has no include directories or defines')
    if not re.fullmatch(r'[A-Za-z][A-Za-z_0-9]*', library):
        raise ValueError('unsupported VHDL library name')
    if frontend == 'ghdl':
        std = std or '08'
        if std not in ('87', '93', '93c', '00', '02', '08', '19'):
            raise ValueError(f'unsupported VHDL standard {std!r}')
    out = Path(out).absolute()
    sources = [Path(p).absolute() for p in sources]
    if not sources or out.resolve() in {p.resolve() for p in sources}:
        raise ValueError('supply sources; output must not alias an input')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rvw-hdl-') as private:
        private = Path(private).resolve()
        capture = Capture(private / 'inputs')
        tool = capture.tool(yosys)
        rtl = {}
        if frontend == 'chisel':
            from . import hdl_chisel
            if len(sources) != 1:
                raise ValueError('pass one FIRRTL file (one circuit)')
            inputs = [capture.file(p) for p in sources]
            fir_tool = capture.tool(firtool or os.environ.get('RVW_FIRTOOL') or 'firtool')
            rtldir = private / 'rtl'
            rtldir.mkdir()
            process = run_group(hdl_chisel.firtool_argv(fir_tool.path, inputs[0].copy, rtldir),
                                cwd=private, capture=True, timeout=timeout)
            if process.returncode:
                raise ValueError('firtool failed: ' + process.stderr[-3000:])
            copies, includes = hdl_chisel.emitted(rtldir), []
            for c in copies:
                if re.search(r'`include\b|' + SOURCE_REMAP, c.read_text()):
                    raise ValueError('unsupported include, file input or source remapping in firtool output')
            rtl = {f'rtl/{c.name}': c.read_text() for c in copies}
            # Capture each Scala file that a location names, under the source roots.
            roots = [Path(r).absolute() for r in source_roots] or [Path(sources[0]).parent]
            scala = {}
            for rel in sorted(hdl_chisel.scala_paths(rtl.values())):
                found = hdl_chisel.resolve_scala(rel, roots)
                if found is not None:
                    scala[rel] = capture.file(found)
            used = [*inputs, *scala.values()]
        elif frontend in ('yosys', 'ghdl'):
            inputs = [capture.file(p) for p in sources]
            copies, includes, used = [i.copy for i in inputs], [], inputs
            # Refuse file access whose dependency set this subset cannot capture.
            for item in inputs if frontend == 'yosys' else ():
                if re.search(r'`include\b|' + SOURCE_REMAP, item.copy.read_text()):
                    raise ValueError('unsupported include, file input or source remapping')
            if frontend == 'ghdl':
                from . import hdl_ghdl
                plugin = capture.file(hdl_ghdl.plugin_path(tool, ghdl_plugin))
                ghdl_tool = capture.tool('ghdl')
        else:
            from .hdl_slang import capture_sources
            copies, includes, used = capture_sources(capture, sources, include_dirs)
            for path in copies:
                if re.search(SOURCE_REMAP, strip_comments(path.read_text(errors='replace'))):
                    raise ValueError('unsupported file input or source remapping')
            plugin = capture.file(_slang_plugin(tool, slang))
        paths = {os.path.realpath(i.copy): i.source for i in used}
        for c in (copies if frontend == 'chisel' else ()):
            paths[os.path.realpath(c)] = f'rtl/{c.name}'
        netlist = private / 'design.json'
        script = private / 'build.ys'
        ast = locs = None
        automatic = set()
        env = None
        if frontend == 'ghdl':
            prefix = hdl_ghdl.ghdl_prefix(tool)
            env = {**os.environ, **({'GHDL_PREFIX': prefix} if prefix else {})}
            options = [f'--std={std}', f'--work={library}', *(f'-g{g}' for g in parameters)]
            if any(re.search(r'\s|"', str(c)) for c in copies):
                raise ValueError('source paths must not contain spaces or quotes')
            xmldir = private / 'xml'
            xmldir.mkdir()
            process = run_group([ghdl_tool.path, '--file-to-xml', f'--std={std}', f'--work={library}',
                                 *map(str, copies)], cwd=xmldir, capture=True, timeout=timeout)
            if process.returncode:
                raise ValueError('VHDL analysis failed: ' + process.stderr[-3000:])
            locs = hdl_ghdl.locations(process.stdout)
            script.write_text('ghdl ' + ' '.join(options) + ' ' + ' '.join(str(c) for c in copies)
                              + f' -e {top}\nwrite_json {_quote(netlist)}\n')
            argv = [tool.path, '-Q', '-T', '-m', str(plugin.resolved), '-s', str(script)]
        elif frontend in ('yosys', 'chisel'):
            # firtool guards simulation-only initializers with SYNTHESIS.
            define = '-DSYNTHESIS ' if frontend == 'chisel' else ''
            script.write_text(f'read_verilog -sv {define}' + ' '.join(_quote(c) for c in copies)
                              + f'\nhierarchy -check -top {top}\nproc\n'
                              # Chisel resets are synchronous mux logic; opt_dff folds them into $sdff.
                              + ('opt_dff -nodffe -nosdff\nopt_dff -nodffe\n' if frontend == 'chisel' else '')
                              + f'write_json {_quote(netlist)}\n')
            argv = [tool.path, '-Q', '-T', '-s', str(script)]
        else:
            # read_slang takes words without quote removal; the private copies have plain paths.
            if any(re.search(r'\s|"', str(c)) for c in (*copies, *includes)):
                raise ValueError('source and include paths must not contain spaces or quotes')
            options = [f'--top {top}', *(f'-I {i}' for i in includes),
                       *(f'-D {d}' for d in defines), *(f'-G{g}' for g in parameters),
                       *([f'--std {std}'] if std else []), '--ignore-assertions', '--ignore-initial',
                       ' '.join(str(c) for c in copies)]
            argv = [tool.path, '-Q', '-T', '-m', str(plugin.resolved), '-s', str(script)]
            astscript = private / 'ast.ys'
            astscript.write_text('read_slang --dump-ast --ast-compilation-only ' + ' '.join(options) + '\n')
            process = run_group([tool.path, '-q', '-Q', '-T', '-m', str(plugin.resolved), '-s', str(astscript)],
                                cwd=private, capture=True, timeout=timeout)
            if process.returncode:
                raise ValueError('HDL elaboration failed: ' + ((process.stdout or '') + process.stderr)[-3000:])
            from .hdl_slang import automatic_locals, instances, parse_ast
            parsed = parse_ast(process.stdout)
            ast = instances(parsed)
            automatic = automatic_locals(parsed)
            script.write_text('read_slang --keep-hierarchy ' + ' '.join(options)
                              + f'\nhierarchy -top {top}\nproc\nwrite_json {_quote(netlist)}\n')
        process = run_group(argv, cwd=private, env=env, capture=True, timeout=timeout)
        if process.returncode:
            raise ValueError('HDL elaboration failed: ' + ((process.stdout or '')[-1500:] + process.stderr)[-3000:])
        data = json.loads(netlist.read_text())
        fd, name = tempfile.mkstemp(prefix='.rvw-hdl-', suffix='.db', dir=out.parent)
        os.close(fd)
        temp = Path(name)
        try:
            conn = sqlite3.connect(temp)
            try:
                conn.executescript(schema_sql())
                rename = {}
                if locs:
                    rename = {m: e for m in data['modules']
                              if (e := hdl_ghdl.entity_of(m, locs['entities'])) is not None}
                writer = _Writer(conn, data, paths, base=private, types=ast[1] if ast else {}, rename=rename, automatic=automatic)
                writer.instance(top, '', None)
                writer.domains()
                _artifact(conn, "hdl/port-connections.json", writer.port_connections)
                if locs:
                    hdl_ghdl.apply(conn, locs, paths)
                if frontend == 'chisel':
                    names, hgldd = hdl_chisel.load_hgldd(private / 'rtl')
                    bound = hdl_chisel.apply(conn, rtl, {k: v.source for k, v in scala.items()}, names)
                    for name, text in rtl.items():
                        data = text.encode()
                        conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                                     (name, 'text/x-systemverilog', 'identity', len(data), data))
                    for name, data in hgldd.items():
                        conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                                     (name, 'application/json', 'identity', len(data), data))
                    _artifact(conn, 'hdl/source-map.json',
                              {n: {str(k): [f'{f}:{l}' for f, l in v] for k, v in hdl_chisel.line_map(t).items()}
                               for n, t in rtl.items()})
                meta = {'schema': 'rvw.designdb/20', 'toplevel': top,
                        'frontend': FRONTENDS[frontend], 'extra_scopes': f'TOP {top}',
                        'emission_config': '$incomplete:hdl-navigation-only',
                        'input_capture': json.dumps(capture.record()),
                        'graph_semantics': 'conservative signal and whole-cell dependencies; register stage counts can include state aliases',
                        'yosys_version': tool.version.strip(),
                        'hdl_port_connection_coverage': 'all-instance-ports'}
                if frontend == 'chisel':
                    meta.update({'firtool_version': fir_tool.version.strip(),
                                 'firtool_options': json.dumps(hdl_chisel.FIRTOOL_OPTIONS),
                                 'hdl_options': json.dumps({'source_roots': [str(r) for r in roots]})})
                if frontend == 'ghdl':
                    meta.update({'ghdl_plugin_sha256': plugin.sha256, 'ghdl_version': ghdl_tool.version.strip(),
                                 'hdl_options': json.dumps({'std': std, 'library': library,
                                                            'parameters': list(parameters)})})
                if frontend == 'slang':
                    meta.update({'slang_plugin_sha256': plugin.sha256,
                                 'hdl_options': json.dumps({'include_dirs': [str(Path(d).absolute()) for d in include_dirs],
                                                            'defines': list(defines), 'parameters': list(parameters),
                                                            'std': std})})
                conn.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
                for item in used:
                    conn.execute('INSERT OR IGNORE INTO input_files VALUES (?,?,?,?,?)',
                                 (item.source, item.resolved, item.sha256, item.size,
                                  json.dumps({'source': item.source, 'sha256': item.sha256})))
                if ast:
                    _artifact(conn, 'hdl/parameters.json', {p: ast[0][p] for p in sorted(ast[0])
                                                            if p in writer.components})
                # The SpinalBlocks diagram of the same database (`rvw query export blocks`).
                from .blocks import blocks
                raw = json.dumps(blocks(conn), separators=(',', ':')).encode()
                conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                             ('blocks.json', 'application/json', 'gzip', len(raw), gzip.compress(raw, mtime=0)))
                conn.execute('INSERT INTO warnings VALUES (?,?)', ('hdl',
                             'Conservative lowered graph. No semantic diff or blackbox support.'))
                conn.commit()
            finally:
                conn.close()
            os.replace(temp, out)
        finally:
            temp.unlink(missing_ok=True)
    return {'db': str(out), 'frontend': FRONTENDS[frontend], 'top': top}


def _artifact(conn, name, value):
    data = json.dumps(value, indent=1, sort_keys=True).encode()
    conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', (name, 'application/json', 'identity', len(data), data))


def _dotted(path):
    """The reader's normal form of an RTL path: `g[1].u.q` is queried as `g.1.u.q`."""
    return re.sub(r'\[(\d+)\]', r'.\1', path)


class _Writer:
    def __init__(self, conn, data, paths, base=None, types=None, rename=None, automatic=()):
        self.c = conn
        self.modules = data['modules']
        self.paths = paths
        self.base = base
        self.types = types or {}
        self.automatic = set(automatic)
        self.components = {}
        self.port_connections = {}
        self.rename = rename or {}
        self.files = {}
        self.sid = self.cid = self.aid = 0
        self.active = set()
        self.state = []  # (output signal ids, clock id, edge, reset id, reset kind, active high, reset bit)
        self.vectors = []  # (visible net id, its bit node ids) for per-net reset values

    def loc(self, attrs):
        src = attrs.get('src', '').split('|')[0]
        match = re.match(r'(.+?):(\d+)(?:\.\d+)?(?:-[\d.]+)?$', src)
        if not match:
            return None, None
        name = match[1]
        if self.base is not None:
            name = os.path.realpath(os.path.join(self.base, name))
        path = self.paths.get(name)
        if path is None:
            raise ValueError(f'uncaptured source: {src}')
        if path not in self.files:
            self.files[path] = len(self.files) + 1
            self.c.execute('INSERT INTO files VALUES (?,?)', (self.files[path], path))
        return self.files[path], int(match[2])

    def signal(self, cid, path, name, width=1, direction=None, generated=False, attrs=None, kind='wire', spinal=None):
        self.sid += 1
        fid, line = self.loc(attrs or {})
        self.c.execute('''INSERT INTO signals
            (id,component_id,name,path,spinal_path,kind,direction,type,width,generated,file_id,line,tags)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (self.sid,cid,name,path,spinal or _dotted(path),kind,direction,'Bits',width,int(generated),fid,line,
             '$incomplete:hdl-navigation-only' + (' hdl:automatic-local' if path in self.automatic else '')))
        if path in self.types:
            self.c.execute('UPDATE signals SET type=? WHERE id=?', (self.types[path], self.sid))
        return self.sid

    def edge(self, src, dst, kind='data'):
        if src != dst:
            self.c.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?)', (src,dst,kind))

    def assignment(self, cid, target, reads, source, attrs):
        self.aid += 1
        fid, line = self.loc(attrs)
        self.c.execute('''INSERT INTO assignments
            (id,target_id,component_id,kind,source,key,seq,file_id,line) VALUES (?,?,?,?,?,?,?,?,?)''',
            (self.aid,target,cid,'data',source,'$incomplete:lowered-cell',self.aid,fid,line))
        for sid, kind in set(reads):
            self.c.execute('INSERT INTO assign_reads VALUES (?,?,?)', (self.aid,sid,kind))
            # A cell that reads its own output is a real loop (SpinalDB keeps self-edges too).
            self.c.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?)', (sid,target,kind))

    def instance(self, module, path, parent, depth=0, cell=None):
        if module in self.active:
            raise ValueError('recursive hierarchy')
        self.active.add(module)
        m = self.modules[module]
        if any(int(m.get('attributes', {}).get(k, '0'), 2) for k in ('blackbox','whitebox')):
            raise ValueError('unsupported blackbox')
        if m.get('processes'):
            raise ValueError('unsupported unlowered process')
        if any(p['direction'] == 'inout' for p in m['ports'].values()):
            raise ValueError('unsupported inout')
        self.cid += 1
        cid = self.cid
        self.components[path] = cid
        fid, line = self.loc(m.get('attributes', {}))
        # yosys-slang names each kept instance `module$top.path`; the module is the prefix.
        name = module.split('$', 1)[0] if '$' in module[1:] and not module.startswith('$') else module
        name = self.rename.get(module, name)
        self.c.execute('''INSERT INTO components
            (id,parent_id,path,name,module,depth,file_id,line,tags) VALUES (?,?,?,?,?,?,?,?,?)''',
            (cid,parent,path,cell or name,name,
             _dotted(path).count('.')+1 if path else 0,fid,line,'$incomplete:hdl-navigation-only' + (' hdl:automatic-local' if path in self.automatic else '')))
        prefix = path + '.' if path else ''
        bits = sorted({b for n in m['netnames'].values() for b in n['bits'] if isinstance(b,int)})
        named = {}
        for name, net in m['netnames'].items():
            direction = m['ports'].get(name,{}).get('direction')
            direction = {'input':'in','output':'out'}.get(direction)
            sid = self.signal(cid,prefix+name,name,len(net['bits']),direction,
                              bool(net.get('hide_name')),net.get('attributes'))
            named[name] = sid
        mems = {}
        for memid, mem in (m.get('memories') or {}).items():
            fid, line = self.loc(mem.get('attributes', {}))
            sid = self.signal(cid, prefix + memid, memid, mem['width'], None, bool(mem.get('hide_name')),
                              mem.get('attributes'), kind='mem')
            self.c.execute('INSERT INTO memories(id,signal_id,component_id,name,path,width,depth,key,file_id,line) '
                           'VALUES (?,?,?,?,?,?,?,?,?,?)', (sid, sid, cid, memid, prefix + memid, mem['width'],
                                                            mem['size'], '$incomplete:hdl-memory', fid, line))
            mems[memid] = sid
        # Reuse unique scalar declarations as graph vertices. This avoids an
        # artificial alias cycle for the common scalar case.
        bitids = {}
        owners = {}
        for nn, net in m['netnames'].items():
            for b in net['bits']:
                if isinstance(b, int):
                    owners.setdefault(b, []).append(nn)
        for b in bits:
            aliases = list(dict.fromkeys(owners.get(b, [])))
            # Prefer the one visible scalar name; hidden Yosys temporaries stay aliases of it.
            visible = [nn for nn in aliases if not m['netnames'][nn].get('hide_name')]
            if len(visible) == 1 and len(aliases) > 1:
                aliases = visible
            if len(aliases) == 1 and len(m['netnames'][aliases[0]]['bits']) == 1:
                bitids[b] = named[aliases[0]]
            else:
                # Name a shared bit after one owning net: `rdata_q[3]` (query name `rdata_q.3`).
                owner = (visible or aliases or [None])[0]
                label = f'$bit${b}'
                if owner is not None and f'{owner}[0]' not in m['netnames']:
                    net = m['netnames'][owner]
                    index = net['bits'].index(b)
                    if net.get('upto'):
                        index = len(net['bits']) - 1 - index
                    index += net.get('offset', 0)
                    label = f'{owner}[{index}]'
                bitids[b] = self.signal(cid,prefix+label,label,generated=True,
                                        spinal=_dotted(prefix+label))
        for name, net in m['netnames'].items():
            if not net.get('hide_name') and all(isinstance(b, int) for b in net['bits']):
                self.vectors.append((named[name], [bitids[b] for b in net['bits']]))
        for name, net in m['netnames'].items():
            sid = named[name]
            reads = [(bitids[b],'data') for b in net['bits'] if isinstance(b,int) and bitids[b] != sid]
            for bid, _ in reads:
                self.edge(sid,bid)
                self.edge(bid,sid)
            if reads or not any(isinstance(b,int) for b in net['bits']):
                self.assignment(cid,sid,reads,'Yosys net alias',net.get('attributes',{}))
        for name, cell in m['cells'].items():
            typ = cell['type']
            ports = cell['connections']
            if typ in self.modules:
                child_bits = self.instance(typ,prefix+name,cid,depth+1,name)
                bindings = []
                self.port_connections[prefix + name] = bindings
                for port, child_port in self.modules[typ]['ports'].items():
                    parent_bits = ports.get(port, [])
                    bindings.append({'name': port, 'direction': child_port['direction'],
                                     'width': len(child_port['bits']),
                                     'status': ('unconnected' if not parent_bits else
                                                'tied' if all(b in ('0', '1') for b in parent_bits) else
                                                'unknown' if any(isinstance(b, str) for b in parent_bits) else 'connected'),
                                     'bits_lsb_first': [b if isinstance(b, str) else None for b in parent_bits]})
                    if not parent_bits:
                        continue
                    if len(parent_bits) != len(child_port['bits']):
                        raise ValueError('port width mismatch')
                    for pb, cb in zip(parent_bits,child_port['bits']):
                        if isinstance(pb,int) and isinstance(cb,int):
                            a,b = bitids[pb],child_bits[cb]
                            self.edge(a,b) if child_port['direction']=='input' else self.edge(b,a)
                        elif child_port['direction']=='input' and isinstance(cb,int) and not isinstance(pb,int):
                            # A constant on a child input: the child bit is tied.
                            self.assignment(cid,child_bits[cb],[],f'Yosys constant {pb}',cell.get('attributes',{}))
                        elif child_port['direction']=='output' and isinstance(pb,int) and not isinstance(cb,int):
                            # A child output driven by a constant inside the child.
                            self.assignment(cid,bitids[pb],[],f'Yosys constant {cb}',cell.get('attributes',{}))
                continue
            base = typ.removeprefix('$')
            if typ == '$scopeinfo':
                continue
            if typ.startswith('$') and base in MEMORY:
                self._memory_cell(cid, cell, base, bitids, mems)
                continue
            if not typ.startswith('$') or base not in COMB | STATE:
                raise ValueError(f'unsupported cell: {typ}')
            directions = cell.get('port_directions',{})
            if set(directions) != set(ports) or set(directions.values()) - {'input','output'}:
                raise ValueError(f'unsupported ports: {typ}')
            reads = []
            for port, bb in ports.items():
                if directions[port]=='input':
                    # Clock and reset pins are clock-domain controls (table clock_domains), not data.
                    if base in STATE and port in {'CLK','C','ARST','SRST','ALOAD'}:
                        continue
                    kind = 'sel' if port in {'S','EN','E','ARST','SRST','ALOAD'} else 'data'
                    reads.extend((bitids[b],kind) for b in bb if isinstance(b,int))
            attrs = cell.get('attributes',{})
            outs = [b for port, bb in ports.items() if directions[port]=='output' for b in bb if isinstance(b,int)]
            bitwise = base in {'buf', 'pos'} and len(ports.get('A', [])) == len(outs)
            if not bitwise and len(outs) > 1 and len(reads) > 1:
                # One hidden hub per cell keeps the whole-cell dependency linear in its ports.
                hub = self.signal(cid,prefix+f'$cell${self.sid+1}',f'$cell${self.sid+1}',generated=True)
                self.assignment(cid,hub,reads,typ,attrs)
                reads = [(hub,'data')]
            for i, b in enumerate(outs):
                if bitwise:
                    a = ports['A'][i]
                    reads = [(bitids[a],'data')] if isinstance(a,int) else []
                self.assignment(cid,bitids[b],reads,typ if reads or not bitwise else f'Yosys constant {a}',attrs)
                if base in STATE:
                    visible = [named[nn] for nn in dict.fromkeys(owners.get(b, []))
                               if not m['netnames'][nn].get('hide_name')]
                    self._state(cell, base, bitids, b, visible, i)
                    self.c.execute("UPDATE signals SET kind='reg' WHERE id=?",(bitids[b],))
                    for v in visible:
                        self.c.execute("UPDATE signals SET kind='reg' WHERE id=?",(v,))
        self.active.remove(module)
        return bitids

    def _prefix(self, cid):
        path = next(p for p, c in self.components.items() if c == cid)
        return path + '.' if path else ''

    def _memory_cell(self, cid, cell, base, bitids, mems):
        """Memory ports: writes drive the memory node, reads depend on it and on the address."""
        ports, params = cell['connections'], cell.get('parameters', {})
        memid = str(params.get('MEMID', '')).removeprefix('\\')
        if memid not in mems:
            raise ValueError(f'memory port of unknown memory: {memid}')
        mem = mems[memid]
        bits = lambda port: [bitids[b] for b in ports.get(port, []) if isinstance(b, int)]
        fid, line = self.loc(cell.get('attributes', {}))
        attrs = cell.get('attributes', {})
        if base.startswith('meminit'):
            self.c.execute("UPDATE memories SET init_words=coalesce(init_words,0)+? WHERE signal_id=?",
                           (int(str(params.get('WORDS', '1')), 2) if set(str(params.get('WORDS', '1'))) <= {'0', '1'}
                            else int(params.get('WORDS', 1)), mem))
            return
        clocked = str(params.get('CLK_ENABLE', '0')).strip('0') != ''
        if base.startswith('memwr'):
            reads = [(b, 'data') for b in bits('DATA')] + [(b, 'sel') for b in bits('ADDR') + bits('EN')]
            self.aid += 1
            self.c.execute('''INSERT INTO assignments (id,target_id,component_id,kind,source,key,seq,file_id,line)
                VALUES (?,?,?,?,?,?,?,?,?)''', (self.aid, mem, cid, 'mem_write', cell['type'],
                                                '$incomplete:lowered-cell', self.aid, fid, line))
            for sid, kind in set(reads):
                self.c.execute('INSERT INTO assign_reads VALUES (?,?,?)', (self.aid, sid, kind))
                self.c.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?)', (sid, mem, kind))
            kind = 'write'
        else:
            reads = [(mem, 'data')] + [(b, 'sel') for b in bits('ADDR') + bits('EN')]
            if len(bits('DATA')) > 1:
                hub = self.signal(cid, f'{self._prefix(cid)}$cell${self.sid+1}', f'$cell${self.sid+1}', generated=True)
                self.assignment(cid, hub, reads, cell['type'], attrs)
                reads = [(hub, 'data')]
            for b in bits('DATA'):
                self.assignment(cid, b, reads, cell['type'], attrs)
                if clocked:
                    self.c.execute("UPDATE signals SET kind='reg' WHERE id=?", (b,))
            kind = 'read_sync' if clocked else 'read_async'
        self.c.execute('INSERT INTO mem_ports(memory_id,component_id,kind,key,file_id,line) VALUES (?,?,?,?,?,?)',
                       (mem, cid, kind, '$incomplete:hdl-memory-port', fid, line))

    def _state(self, cell, base, bitids, bit, names, index=0):
        """Record the clock and reset of one flip-flop output bit."""
        ports, params = cell['connections'], cell.get('parameters', {})

        def one(port):
            bb = [b for b in ports.get(port, []) if isinstance(b, int)]
            return bitids[bb[0]] if len(bb) == 1 else None

        def flag(name, default=1):
            v = params.get(name)
            return default if v is None else int(str(v), 2) if set(str(v)) <= {'0', '1'} else int(v)

        clock = one('CLK') if 'CLK' in ports else one('EN') if base in {'dlatch', 'adlatch'} else None
        if base in {'adff', 'adffe', 'adlatch'}:
            reset, kind, high, value = one('ARST'), 'ASYNC', flag('ARST_POLARITY'), params.get('ARST_VALUE')
        elif base in {'aldff', 'aldffe'}:
            # An async load of a constant is an async reset; a variable load value stays unknown.
            ad = ports.get('AD', [])
            value = ''.join(str(b) for b in reversed(ad)) if all(not isinstance(b, int) for b in ad) else None
            reset, kind, high = one('ALOAD'), 'ASYNC', flag('ALOAD_POLARITY')
        elif base in {'sdff', 'sdffe', 'sdffce'}:
            reset, kind, high, value = one('SRST'), 'SYNC', flag('SRST_POLARITY'), params.get('SRST_VALUE')
        else:
            reset, kind, high, value = None, 'BOOT', None, None
        edge = 'RISING' if flag('CLK_POLARITY' if 'CLK' in ports else 'EN_POLARITY') else 'FALLING'
        # Reset values are MSB-first strings for the whole cell; keep this output bit's char.
        value = str(value) if value is not None else None
        char = value[len(value) - 1 - index] if value and index < len(value) else None
        self.state.append(([bitids[bit], *names], clock, edge, reset, kind, high, char))

    def _root(self, sid):
        """(toplevel input, inverted) behind a control net, through ports, aliases, buffers and
        inverters. A net derived by other logic is its own root: (net, False)."""
        if sid is None:
            return None, False
        pending, seen = [(sid, False)], set()
        while pending:
            n, inv = pending.pop(0)
            if n in seen:
                continue
            seen.add(n)
            row = self.c.execute('SELECT s.direction, c.depth FROM signals s JOIN components c '
                                 'ON c.id=s.component_id WHERE s.id=?', (n,)).fetchone()
            if row == ('in', 0):
                return n, inv
            sources = {r[0] for r in self.c.execute('SELECT source FROM assignments WHERE target_id=?', (n,))}
            cells = {x for x in sources if x != 'Yosys net alias' and not x.startswith('Yosys constant')}
            if cells - {'$not', '$logic_not', '$buf', '$pos'}:
                continue  # derived by logic: not a plain path to an input
            flip = inv ^ bool(cells & {'$not', '$logic_not'})
            pending.extend((r[0], flip) for r in self.c.execute('SELECT src FROM edges WHERE dst=?', (n,)))
        return sid, False

    def domains(self):
        """Write clock_domains and register domain ids. Sync resets are recorded only where Yosys
        made $sdff cells; resets in plain mux logic stay data."""
        ids, roots, bitreset = {}, {}, {}
        path = lambda i: self.c.execute('SELECT path FROM signals WHERE id=?', (i,)).fetchone()[0]
        for outs, clock, edge, reset, kind, high, value in self.state:
            for i in (clock, reset):
                if i is not None and i not in roots:
                    roots[i] = self._root(i)
            ck, cinv = roots.get(clock, (None, False))
            rk, rinv = roots.get(reset, (None, False))
            if cinv:
                edge = 'FALLING' if edge == 'RISING' else 'RISING'
            if rinv and high is not None:
                high = not high
            key = (ck, edge, rk, kind, high)
            if key not in ids:
                ids[key] = len(ids) + 1
                cp, rp = (path(ck) if ck else None), (path(rk) if rk else None)
                self.c.execute('INSERT INTO clock_domains(id,clock,reset,reset_kind,reset_active_high,clock_edge,'
                               'clock_key,reset_key) VALUES (?,?,?,?,?,?,?,?)',
                               (ids[key], cp, rp, kind if rp else 'BOOT',
                                None if rp is None else ('true' if high else 'false'), edge,
                                cp + ':Bool' if cp else None, rp + ':Bool' if rp else None))
                if ck:
                    self.c.execute("UPDATE signals SET clock_role='clock' WHERE id=?", (ck,))
                if rk:
                    self.c.execute("UPDATE signals SET clock_role='reset' WHERE id=?", (rk,))
            self.c.execute('UPDATE signals SET clock_domain_id=?, reset_value=? WHERE id=?',
                           (ids[key], value if rk else None, outs[0]))
            for o in outs[1:]:
                self.c.execute('UPDATE signals SET clock_domain_id=? WHERE id=?', (ids[key], o))
            if rk and value is not None:
                bitreset[outs[0]] = value
        # A visible register net's reset value is the concatenation of its bits (MSB first).
        for sid, bits in self.vectors:
            chars = [bitreset.get(b) for b in reversed(bits)]
            value = ''.join(chars) if bits and None not in chars else None
            self.c.execute("UPDATE signals SET reset_value=? WHERE id=? AND kind='reg'", (value, sid))
