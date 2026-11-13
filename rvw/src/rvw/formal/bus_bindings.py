"""Generate simple-bus monitors and instance binds from captured SpinalDB types."""
import json
import re
from pathlib import Path
from rvw.query.db import DesignDB, QueryError
from .simple_bus_checks import render

TYPES = {
    'Axi4': 'axi4', 'spinal.lib.bus.amba4.axi.Axi4': 'axi4',
    'AxiLite4': 'axi_lite4', 'spinal.lib.bus.amba4.axilite.AxiLite4': 'axi_lite4',
    'spinal.lib.bus.tilelink.Bus': 'tilelink', 'tilelink.Bus': 'tilelink',
    'spinal.lib.bus.amba3.apb.Apb3': 'apb',
    'spinal.lib.bus.amba3.ahblite.AhbLite3': 'ahb_lite',
    'Apb3': 'apb',
    'AhbLite3': 'ahb_lite',
    'Axi4StreamBundle': 'axis',
}
PATH = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')


def generate(db, out):
    rows, sources, binds = [], [], []
    with_db = DesignDB(db)
    try:
        c = with_db.conn
        for bid, cid, path, cls, parent in c.execute('SELECT id,component_id,path,class_name,parent_id FROM bundles ORDER BY id').fetchall():
            if cls not in TYPES:
                if cls.endswith('Bus') or cls in ('Bmb', 'Wishbone', 'AvalonMM'):
                    rows.append(dict(path=path, component_id=cid, class_name=cls,
                                     status='unsupported', reason='bus type has no registered checker; simple Bus is ambiguous'))
                continue
            kind = TYPES[cls]
            payload_path = path
            if kind == 'axis':
                stream = c.execute('SELECT path,class_name FROM bundles WHERE id=? AND component_id=?', (parent,cid)).fetchone()
                if stream and stream[1] == 'Stream':
                    path = stream[0]
                else:
                    rows.append(dict(path=path,kind=kind,status='unsupported',reason='AXI4-Stream payload needs its Stream parent'))
                    continue
            row = dict(path=path, component_id=cid, class_name=cls, kind=kind, status='unsupported')
            rows.append(row)
            try:
                sigs = c.execute('SELECT name,path,spinal_path,width,clock_domain_id,pruned FROM signals WHERE component_id=?', (cid,)).fetchall()
                signals = {s[2][len(path)+1:]: s for s in sigs if s[2] and s[2].startswith(path+'.') and not s[5]}
                if not signals:
                    raise ValueError('no unpruned typed signal paths')
                domains = {s[4] for s in signals.values() if s[4] is not None}
                if len(domains) != 1:
                    raise ValueError('bus signals need one recorded clock domain')
                domain = with_db.clock_domain(next(iter(domains)))
                if not domain or not domain.get('reset') or domain.get('edge') != 'RISING' or domain.get('clock_enable') or domain.get('soft_reset'):
                    raise ValueError('requires rising clock, reset, and no clock-enable/soft-reset')
                def ident(s):
                    if not PATH.fullmatch(s):
                        raise ValueError(f'unsupported RTL path {s!r}')
                    return s
                def signal(key, bits=None):
                    if key not in signals:
                        raise ValueError(f'missing bus field {key}')
                    s = signals[key]
                    if not s[3] or (bits is not None and s[3] != bits):
                        raise ValueError(f'unsupported width for {key}')
                    return ident(s[0])
                def payload(keys):
                    if not keys:
                        raise ValueError('empty bus payload')
                    width = sum(signals[k][3] for k in keys)
                    return width, '{'+', '.join(signal(k) for k in sorted(keys))+'}'
                def local_control(path):
                    signal = with_db.resolve_one(path)
                    if signal.width != 1 or signal.pruned:
                        raise ValueError('clock/reset must be one unpruned bit')
                    if signal.component_id == cid:
                        return ident(signal.name)
                    candidates=[]
                    for port in with_db.signals_where("s.component_id=? AND s.direction='in'", (cid,)):
                        sources=with_db.q('SELECT source FROM assignments WHERE target_id=?',(port.id,))
                        reads=with_db.q("SELECT src FROM edges WHERE dst=? AND kind='data'",(port.id,))
                        if sources == [(signal.name,)] and reads == [(signal.id,)]: candidates.append(port)
                    if len(candidates)!=1:
                        raise ValueError('clock/reset needs one direct local control port')
                    return ident(candidates[0].name)
                ports = dict(clk=local_control(domain['clock']), reset=local_control(domain['reset']))
                if domain.get('reset_active') == 'low': ports['reset'] = '~'+ports['reset']
                source = None
                if kind in ('axi4', 'axi_lite4', 'tilelink'):
                    from .typed_bus_checks import render as render_typed
                    source, channel_ports = render_typed(kind, signals, f'rvw_bus_{bid}')
                    ports.update(channel_ports)
                    width = sum(s[3] for s in signals.values())
                    row['coverage'] = 'opcode_safety' if kind == 'tilelink' else 'channel_safety'
                    row['limitations'] = ['No burst accounting, ID ordering, exclusive-operation or coherence scoreboard.']
                elif kind == 'axis':
                    width, data = payload([k for k in signals if k.startswith('payload.')])
                    ports.update(valid=signal('valid',1),ready=signal('ready',1),payload=data)
                elif kind == 'apb':
                    # Multi-select fabrics need one monitor for each subordinate.
                    signal('PSEL', 1)
                    width, data = payload([k for k in signals if k not in ('PSEL','PENABLE','PREADY','PRDATA','PSLVERROR')])
                    ports.update(select=signal('PSEL'),enable=signal('PENABLE',1),ready=signal('PREADY',1),
                                 error=signal('PSLVERROR',1) if 'PSLVERROR' in signals else "1'b0",request=data)
                else:
                    width, data = payload([k for k in signals if k in ('HADDR','HWRITE','HSIZE','HBURST','HPROT','HMASTLOCK')])
                    for required in ('HADDR','HWRITE','HSIZE','HBURST','HPROT','HMASTLOCK'): signal(required)
                    ports.update(select=signal('HSEL',1),ready=signal('HREADY',1),response_error=signal('HRESP',1),
                                 transfer=signal('HTRANS',2),request=data)
                name = f'rvw_bus_{bid}'
                sources.append(source if source is not None else render(kind,width,4).replace('module rvw_'+kind+'(', 'module '+name+'('))
                comp = with_db.component(cid)
                target = ident(with_db.top + ('.'+comp['path'] if comp['path'] else ''))
                binds.append(f'bind {target} {name} {name}_instance('+', '.join(f'.{k}({v})' for k,v in ports.items())+');')
                row.update(status='generated', width=width, ports=ports, target=target)
            except (ValueError, KeyError, TypeError, QueryError) as exc:
                row['reason'] = str(exc)
        report = dict(schema='rvw.bus-checks/1', status='generated' if binds else 'no_checks',
                      buses=rows, complete=bool(binds) and all(r['status'] == 'generated' for r in rows),
                      database=with_db.capture_record(),
                      limits=['No compiler, solver or simulator was run.',
                              'Typed AXI4, AXI-Lite4 and TileLink monitors provide channel safety only.',
                              'Instance bind syntax requires a frontend with SystemVerilog bind support.',
                              'Clock associations must exist in the database. Missing bindings stay unsupported.'])
    finally:
        with_db.close()
    out = Path(out)
    out.mkdir(parents=True,exist_ok=False)
    (out/'monitors.sv').write_text('\n'.join(sources))
    (out/'binds.sv').write_text('\n'.join(binds)+'\n')
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(args):
    try:
        result = generate(args.db,args.out)
        print(json.dumps(result))
        return 0 if result['status'] == 'generated' else 3
    except (ValueError, OSError, QueryError) as exc:
        print(f'bus check generation error: {exc}')
        return 2
