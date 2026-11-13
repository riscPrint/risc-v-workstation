"""Map decode arithmetic, explicit IRQ connectivity and lint domain inventory."""
import json
from pathlib import Path
from rvw.query.db import DesignDB
from rvw.formal.connectivity import resolve,reverse_check
from rvw.lint.structural import analyze
from .model import load,dumps


def audit(source,db_path,bindings,out):
    obj=load(source)
    spec=json.loads(Path(bindings).read_text())
    if set(spec)!={'interrupts','bus_ports'}:raise ValueError('audit bindings need interrupts and bus_ports')
    if set(spec['interrupts'])!={i['name'] for i in obj['interrupts']}:raise ValueError('bind every declared interrupt exactly once')
    expected={'core.bus'}|{r['name']+'.io.bus' for r in obj['regions']}
    if set(spec['bus_ports'])!=expected:raise ValueError('bind every fabric endpoint exactly once')
    ordered=sorted(obj['regions'],key=lambda r:r['base'])
    holes=[];start=0
    for r in ordered:
        if start<r['base']:holes.append(dict(base=start,size=r['base']-start))
        start=r['base']+r['size']
    if start<1<<obj['address_bits']:holes.append(dict(base=start,size=(1<<obj['address_bits'])-start))
    db=DesignDB(db_path)
    try:
        connections=[]
        for name,row in spec['interrupts'].items():
            connections.append(dict(id=name,kind='required',**row))
        endpoints=[]
        for name,ports in spec['bus_ports'].items():
            if set(ports)!={'PADDR','PSEL','PENABLE','PWRITE','PWDATA','PRDATA','PREADY'}:
                raise ValueError('each APB3 endpoint needs all seven required pin paths')
            resolved = {k:db.resolve_one(v) for k,v in ports.items()}
            region = next((r for r in obj['regions'] if name == r['name']+'.io.bus'), None)
            expected_widths = dict(PADDR=(region['size'].bit_length()-1 if region else obj['address_bits']), PSEL=1, PENABLE=1, PWRITE=1, PWDATA=32, PRDATA=32, PREADY=1)
            if any(resolved[k].width != width for k,width in expected_widths.items()):
                raise ValueError('fabric endpoint pin width differs: '+name)
            endpoints.append(dict(name=name,pins={k:v.path for k,v in resolved.items()},protocol_status='assertions_emitted_by_SpinalSoc; execution_not_established_by_audit'))
        result=dict(schema='rvw.soc-audit/1',status='inconclusive',database_sha256=db.input.sha256,
                    decode=dict(map_disjoint=True,method='exact half-open interval arithmetic',unmapped_error_windows=holes,rtl_proof='not_run'),
                    interrupts=[resolve(db,r) for r in connections],reverse_check=reverse_check(db,connections) if connections else None,
                    bus_ports=endpoints,clock_reset=analyze(db),
                    gaps=['RTL decode formal proof','interrupt value-transfer proof; run the exported connections with rvw formal connectivity --run','protocol assertion execution evidence'])
        result['connection'] = connections
        connection_path = Path(str(out)+'.connections.json')
        if Path(out).exists() or connection_path.exists():
            raise ValueError('audit output must be new')
        with connection_path.open('x') as f:f.write(dumps({'connection':connections}))
        with Path(out).open('x') as f:f.write(dumps(result))
        return result
    finally:db.close()
