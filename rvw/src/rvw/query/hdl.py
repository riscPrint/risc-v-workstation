"""Conservative C6 navigation from the native Yosys Verilog/SV subset."""
from __future__ import annotations

from importlib.resources import files
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
            'mux pmux bmux demux slice concat alu fa lcu').split())
STATE = {'dff', 'adff', 'sdff', 'dffe', 'adffe', 'sdffe', 'sdffce', 'dlatch', 'adlatch'}


def schema_sql():
    return files('rvw.query').joinpath('schema.sql').read_text()


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_hdl(sources, top, out, *, yosys='yosys', timeout=120):
    """Capture, elaborate, translate and atomically publish. Errors keep old output."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9$]*', top):
        raise ValueError('unsupported top module name')
    out = Path(out).absolute()
    sources = [Path(p).absolute() for p in sources]
    if not sources or out.resolve() in {p.resolve() for p in sources}:
        raise ValueError('supply sources; output must not alias an input')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rvw-hdl-') as private:
        private = Path(private)
        capture = Capture(private / 'inputs')
        inputs = [capture.file(p) for p in sources]
        # Refuse file access whose dependency set this subset cannot capture.
        for item in inputs:
            text = item.copy.read_text()
            if re.search(r'`include\b|\$(?:readmem\w*|fopen)\b|`line\b', text):
                raise ValueError('unsupported include, file input or source remapping')
        tool = capture.tool(yosys)
        netlist = private / 'design.json'
        script = private / 'build.ys'
        script.write_text('read_verilog -sv ' + ' '.join(_quote(i.copy) for i in inputs)
                          + f'\nhierarchy -check -top {top}\nproc\nwrite_json {_quote(netlist)}\n')
        process = run_group([tool.path, '-Q', '-T', '-s', str(script)], capture=True, timeout=timeout)
        if process.returncode:
            raise ValueError('HDL elaboration failed: ' + process.stderr[-3000:])
        data = json.loads(netlist.read_text())
        fd, name = tempfile.mkstemp(prefix='.rvw-hdl-', suffix='.db', dir=out.parent)
        os.close(fd)
        temp = Path(name)
        try:
            conn = sqlite3.connect(temp)
            try:
                conn.executescript(schema_sql())
                writer = _Writer(conn, data, {str(i.copy): i.source for i in inputs})
                writer.instance(top, '', None)
                meta = {'schema': 'rvw.designdb/20', 'toplevel': top,
                        'frontend': 'yosys-verilog', 'extra_scopes': f'TOP {top}',
                        'emission_config': '$incomplete:hdl-navigation-only',
                        'input_capture': json.dumps(capture.record()),
                        'graph_semantics': 'conservative signal and whole-cell dependencies'}
                conn.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
                for item in inputs:
                    conn.execute('INSERT INTO input_files VALUES (?,?,?,?,?)',
                                 (item.source, item.resolved, item.sha256, item.size,
                                  json.dumps({'source': item.source, 'sha256': item.sha256})))
                conn.execute('INSERT INTO warnings VALUES (?,?)', ('hdl',
                             'Conservative lowered graph. No semantic diff, memory or blackbox support.'))
                conn.commit()
            finally:
                conn.close()
            os.replace(temp, out)
        finally:
            temp.unlink(missing_ok=True)
    return {'db': str(out), 'frontend': 'yosys-verilog', 'top': top}


class _Writer:
    def __init__(self, conn, data, paths):
        self.c = conn
        self.modules = data['modules']
        self.paths = paths
        self.files = {}
        self.sid = self.cid = self.aid = 0
        self.active = set()

    def loc(self, attrs):
        src = attrs.get('src', '').split('|')[0]
        match = re.match(r'(.+):(\d+)\.\d+', src)
        if not match:
            return None, None
        path = self.paths.get(match[1])
        if path is None:
            raise ValueError(f'uncaptured source: {src}')
        if path not in self.files:
            self.files[path] = len(self.files) + 1
            self.c.execute('INSERT INTO files VALUES (?,?)', (self.files[path], path))
        return self.files[path], int(match[2])

    def signal(self, cid, path, name, width=1, direction=None, generated=False, attrs=None, kind='wire'):
        self.sid += 1
        fid, line = self.loc(attrs or {})
        self.c.execute('''INSERT INTO signals
            (id,component_id,name,path,spinal_path,kind,direction,type,width,generated,file_id,line,tags)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (self.sid,cid,name,path,path,kind,direction,'Bits',width,int(generated),fid,line,
             '$incomplete:hdl-navigation-only'))
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
            self.edge(sid,target,kind)

    def instance(self, module, path, parent):
        if module in self.active:
            raise ValueError('recursive hierarchy')
        self.active.add(module)
        m = self.modules[module]
        if any(int(m.get('attributes', {}).get(k, '0'), 2) for k in ('blackbox','whitebox')):
            raise ValueError('unsupported blackbox')
        if m.get('memories') or m.get('processes'):
            raise ValueError('unsupported memory or unlowered process')
        if any(p['direction'] == 'inout' for p in m['ports'].values()):
            raise ValueError('unsupported inout')
        self.cid += 1
        cid = self.cid
        fid, line = self.loc(m.get('attributes', {}))
        self.c.execute('''INSERT INTO components
            (id,parent_id,path,name,module,depth,file_id,line,tags) VALUES (?,?,?,?,?,?,?,?,?)''',
            (cid,parent,path,path.rsplit('.',1)[-1] or module,module,
             path.count('.')+1 if path else 0,fid,line,'$incomplete:hdl-navigation-only'))
        prefix = path + '.' if path else ''
        bits = sorted({b for n in m['netnames'].values() for b in n['bits'] if isinstance(b,int)})
        bitids = {b:self.signal(cid,prefix+f'$bit${b}',f'$bit${b}',generated=True) for b in bits}
        named = {}
        for name, net in m['netnames'].items():
            direction = m['ports'].get(name,{}).get('direction')
            direction = {'input':'in','output':'out'}.get(direction)
            sid = self.signal(cid,prefix+name,name,len(net['bits']),direction,
                              bool(net.get('hide_name')),net.get('attributes'))
            named[name] = sid
            for b in net['bits']:
                if isinstance(b,int):
                    self.edge(sid,bitids[b])
                    self.edge(bitids[b],sid)
            self.assignment(cid,sid,[(bitids[b],'data') for b in net['bits'] if isinstance(b,int)],
                            'Yosys net alias',net.get('attributes',{}))
        for name, cell in m['cells'].items():
            typ = cell['type']
            ports = cell['connections']
            if typ in self.modules:
                child_bits = self.instance(typ,prefix+name,cid)
                for port, parent_bits in ports.items():
                    child_port = self.modules[typ]['ports'][port]
                    if len(parent_bits) != len(child_port['bits']):
                        raise ValueError('port width mismatch')
                    for pb, cb in zip(parent_bits,child_port['bits']):
                        if isinstance(pb,int) and isinstance(cb,int):
                            a,b = bitids[pb],child_bits[cb]
                            self.edge(a,b) if child_port['direction']=='input' else self.edge(b,a)
                continue
            base = typ.removeprefix('$')
            if not typ.startswith('$') or base not in COMB | STATE:
                raise ValueError(f'unsupported cell: {typ}')
            directions = cell.get('port_directions',{})
            if set(directions) != set(ports) or set(directions.values()) - {'input','output'}:
                raise ValueError(f'unsupported ports: {typ}')
            reads = []
            for port, bb in ports.items():
                if directions[port]=='input':
                    if base in STATE and port in {'CLK','C'}:
                        continue
                    kind = 'sel' if port in {'S','EN','E','ARST','SRST','ALOAD'} else 'data'
                    reads.extend((bitids[b],kind) for b in bb if isinstance(b,int))
            for port, bb in ports.items():
                if directions[port]!='output':
                    continue
                for b in bb:
                    if not isinstance(b,int):
                        continue
                    self.assignment(cid,bitids[b],reads,typ,cell.get('attributes',{}))
                    if base in STATE:
                        self.c.execute("UPDATE signals SET kind='reg' WHERE id=?",(bitids[b],))
                        for nn, net in m['netnames'].items():
                            if b in net['bits']:
                                self.c.execute("UPDATE signals SET kind='reg' WHERE id=?",(named[nn],))
        self.active.remove(module)
        return bitids
