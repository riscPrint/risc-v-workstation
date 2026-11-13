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


def generate(db, out, depth=4, max_beats=256, type_report=None, clocks=None):
    if type(depth) is not int or not 1<=depth<=64:
        raise ValueError("AXI tracker depth must be in 1..64")
    if type(max_beats) is not int or not 1<=max_beats<=256:
        raise ValueError("AXI write strobe history must be in 1..256 beats")
    clock_map={}
    if clocks is not None:
        intent=json.loads(Path(clocks).read_text())
        if not isinstance(intent,dict) or intent.get('schema')!='rvw.bus-clocks/1' or not isinstance(intent.get('instances'),dict):
            raise ValueError('expected rvw.bus-clocks/1 with instances')
        clock_map=intent['instances']
    rows, sources, binds = [], [], []
    with_db = DesignDB(db)
    try:
        c = with_db.conn
        from .bus_types import resolve
        bus_types=resolve(with_db,type_report) if type_report else {}
        for bid, cid, path, cls, parent in c.execute('SELECT id,component_id,path,class_name,parent_id FROM bundles ORDER BY id').fetchall():
            type_info=bus_types.get(bid,{})
            recorded_class=cls
            cls=type_info.get('class_name',cls)
            if cls not in TYPES:
                if cls.endswith('Bus') or cls.split('.')[-1] in ('Bmb','Wishbone','AvalonMM','Axi4ReadOnly','Axi4WriteOnly','Axi4Shared','AxiLite4ReadOnly','AxiLite4WriteOnly'):
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
            if type_info: row.update(recorded_class=recorded_class,type_source=str(type_report),options=type_info.get('options',{}))
            comp = with_db.component(cid)
            component_path=comp['path']
            instance_path=path if not component_path or path.startswith(component_path+'.') else component_path+'.'+path
            row['instance_path']=instance_path
            rows.append(row)
            try:
                sigs = c.execute('SELECT name,path,spinal_path,width,clock_domain_id,pruned FROM signals WHERE component_id=?', (cid,)).fetchall()
                signals = {s[2][len(path)+1:]: s for s in sigs if s[2] and s[2].startswith(path+'.') and not s[5]}
                if not signals:
                    raise ValueError('no unpruned typed signal paths')
                domains = {s[4] for s in signals.values() if s[4] is not None}
                declaration=clock_map.get(instance_path)
                if declaration is not None:
                    if not isinstance(declaration,dict) or set(declaration)!={'clock','reset'}:
                        raise ValueError('bus clock declaration needs exactly clock and reset paths')
                    matches=with_db.q('SELECT id FROM clock_domains WHERE clock=? AND reset=?',
                                      (declaration['clock'],declaration['reset']))
                    if len(matches)!=1:raise ValueError('declared controls need one matching database clock domain')
                    domain_id=matches[0][0]
                    if domains and domains!={domain_id}:raise ValueError('declared clock contradicts recorded bus signal domains')
                    row['clock_source']='project'
                else:
                    if len(domains)!=1:raise ValueError('bus signals need one recorded clock domain or explicit bus clock declaration')
                    domain_id=next(iter(domains));row['clock_source']='database'
                row['clock_domain_id']=domain_id
                domain = with_db.clock_domain(domain_id)
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
                    row['limitations'] = ['No coherence or exclusive memory-reservation model.']
                    if kind in ('axi4','axi_lite4'):
                        try:
                            from .axi_transactions import render as render_transactions
                            body=render_transactions(kind,signals,depth,max_beats)
                            source=source.replace('\nendmodule\n','\n'+body+'\nendmodule\n')
                            row.update(coverage='transaction_safety',tracker_depth=depth,write_history_beats=max_beats,
                                check_groups=['channel_stability','request_bursts','read_ids_beats','write_address_data_order','response_lock']+(['write_strobes'] if kind=='axi4' else []))
                            row['limitations'] += ['Queue capacity failures are instrumentation limits, not protocol violations.',
                                                   'Write burst history is an instrumentation limit. Memory data correctness is not modeled.']
                        except ValueError as exc:
                            row['unbound_checks']=[dict(kind='axi_transactions',reason=str(exc))]
                    else:
                        try:
                            from .tilelink_transactions import render as render_tl
                            body=render_tl(signals,depth,type_info.get('options',{}))
                            source=source.replace('\nendmodule\n','\n'+body+'\nendmodule\n')
                            row.update(coverage='transaction_safety',protocol_profile='tilelink-uh-probe-c',probe_tracker_depth=depth,
                                check_groups=['a_d_sources','burst_headers','request_parameters','response_parameters',
                                              'release_ack','grant_sinks','probe_pairs'] if 'b.valid' in signals else
                                             ['a_d_sources','burst_headers','request_parameters','response_parameters'])
                            row['limitations'] += ['Probe queue capacity is an instrumentation limit.',
                                'Coherent B supports probes. Cache permission/data state and negotiated address regions are not modeled.']
                        except ValueError as exc:
                            row['unbound_checks']=[dict(kind='tilelink_transactions',reason=str(exc))]
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
                target_instance = ident(with_db.top + ('.'+comp['path'] if comp['path'] else ''))
                unique_module=with_db.q('SELECT COUNT(*) FROM components WHERE module=?',(comp['module'],))[0][0]==1
                target = ident(comp['module']) if unique_module else target_instance
                row.update(target_instance=target_instance,bind_scope='unique_module' if unique_module else 'instance')
                binds.append(f'bind {target} {name} {name}_instance('+', '.join(f'.{k}({v})' for k,v in ports.items())+');')
                row.update(status='generated', width=width, ports=ports, target=target)
            except (ValueError, KeyError, TypeError, QueryError) as exc:
                row['reason'] = str(exc)
        used_paths={r.get('instance_path',r['path']) for r in rows}
        rows.extend(dict(path=key,kind='clock_binding',status='unsupported',reason='clock declaration has no matching bus instance')
                    for key in sorted(set(clock_map)-used_paths))
        report = dict(schema='rvw.bus-checks/1', status='generated' if binds else 'no_checks',
                      buses=rows, complete=bool(binds) and all(r['status'] == 'generated' and not r.get('unbound_checks') for r in rows),
                      database=with_db.capture_record(),clock_declarations=clock_map,
                      limits=['No compiler, solver or simulator was run.',
                              'Transaction checks require complete fields. Partial bindings retain per-instance reasons.',
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
        result = generate(args.db,args.out,getattr(args,'depth',4),getattr(args,'max_beats',256),getattr(args,'type_report',None),getattr(args,'clocks',None))
        print(json.dumps(result))
        return 0 if result['status'] == 'generated' else 3
    except (ValueError, OSError, QueryError) as exc:
        print(f'bus check generation error: {exc}')
        return 2
