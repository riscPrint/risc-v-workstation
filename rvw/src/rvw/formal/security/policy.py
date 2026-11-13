"""Source/sink policy binding for the conservative Boolean IFT pass."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

from rvw.common.proc import run_group
from rvw.formal.common import check_ident
from .ift import instrument


def bind(design, top, policy):
    ports = design['modules'][top]['ports']
    clock, reset = policy['clock'], policy['reset']
    sources, sinks = policy.get('sources', []), policy['sinks']
    release = policy.get('declassifier')
    if not (sources or policy.get('internal_sources')) or not sinks or len(set(sources)) != len(sources) or len(set(sinks)) != len(sinks):
        raise ValueError('distinct nonempty sources and sinks required')
    if not policy.get('adversary') or not policy.get('unmodeled_channels'):
        raise ValueError('declare adversary and unmodeled_channels')
    for p in (clock, reset, *([release] if release else [])):
        if p not in ports or ports[p]['direction'] != 'input' or len(ports[p]['bits']) != 1:
            raise ValueError('clock, reset and declassifier must be scalar public inputs')
    if clock == reset or (release and release in (clock, reset)) or set(sources) & {clock, reset, release}:
        raise ValueError('control ports must be public and clock differs from reset')
    if any(p not in ports or ports[p]['direction'] != 'input' for p in sources):
        raise ValueError('sources must be input ports')
    if any(p not in ports or ports[p]['direction'] != 'output' for p in sinks):
        raise ValueError('sinks must be output ports')
    if policy.get('kind', 'secure_path') not in ('secure_path', 'constant_time'):
        raise ValueError('unknown policy kind')
    if policy.get('kind') == 'constant_time' and not policy.get('operations'):
        raise ValueError('constant_time requires declared operations')
    for name in ports:
        check_ident('policy port', name)
    declarations, connections, wires = [], [], []
    for name, port in ports.items():
        width = len(port['bits'])
        declarations.append(f'{port["direction"]} [{width-1}:0] {name}')
        connections.append(f'.{name}({name})')
        if name == clock and any(c['type'] == '$_DFF_P_' for c in design['modules'][top]['cells'].values()):
            continue
        if port['direction'] == 'input':
            connections.append(f'.{name}__t({width}\'b' + ('1'*width if name in sources else '0'*width) + ')')
        else:
            wires.append(f'wire [{width-1}:0] {name}__t;')
            connections.append(f'.{name}__t({name}__t)')
    condition = f'!{reset}' + (f' && !{release}' if release else '')
    assertions = [f'always @(posedge {clock}) if ({condition}) assert ({name}__t == 0);' for name in sinks]
    return (instrument(design, top, state_sources=policy.get('internal_sources', ())) + '\nmodule rvw_secure_path('+', '.join(declarations)+');\n'
            +'\n'.join(wires)+f'\n{top}__ift dut('+', '.join(connections)+');\n'
            +'\n'.join(assertions)+'\nendmodule\n')


def isolation(design, top, policy):
    """Bind an independent, static access policy to observed grant signals.

    Priority follows region order. The first region touched by the access must
    contain the full access. Permissions name each master and privilege value.
    This checks a resolved policy, not CSR decoding or ePMP policy derivation.
    """
    ports=design['modules'][top]['ports']
    signals=policy['signals']
    if len(set(signals.values())) != len(signals) or set(signals.values()) & {policy['clock'], policy['reset']}:
        raise ValueError('access signals must be distinct from each other and reset/clock')
    required={'request':1,'grant':1,'write':1,'execute':1,'privilege':2}
    for key in (*required,'address','master'):
        name=signals[key]
        check_ident('isolation signal',name)
        if name in ports and ports[name]['direction'] != ('output' if key == 'grant' else 'input'):
            raise ValueError('access observations need request inputs and grant output')
        if name not in ports or (key in required and len(ports[name]['bits'])!=required[key]):
            raise ValueError('missing or wrong-width isolation port: '+key)
    address_width=len(ports[signals['address']]['bits'])
    size=policy['access_bytes']
    if type(size) is not int or size<1 or size>1<<address_width:
        raise ValueError('positive fixed access_bytes required')
    if not policy.get('adversary') or not policy.get('unmodeled_channels') or not policy.get('regions'):
        raise ValueError('declare regions, adversary and unmodeled_channels')
    clock,reset=policy['clock'],policy['reset']
    for name in (clock,reset):
        if name not in ports or ports[name]['direction']!='input' or len(ports[name]['bits'])!=1:
            raise ValueError('scalar public clock/reset inputs required')
    decl=[]; con=[]
    for name,port in ports.items():
        check_ident('isolation port',name)
        if name.startswith('rvw_') or port['direction'] not in ('input','output'):
            raise ValueError('reserved port name or inout')
        decl.append(f'{port["direction"]} [{len(port["bits"])-1}:0] {name}')
        con.append(f'.{name}({name})')
    addr=signals['address']; end='rvw_end'
    lines=[f'module rvw_secure_path({", ".join(decl)});',f'{top} dut({", ".join(con)});',
           f'wire [{address_width}:0] {end} = {{1\'b0,{addr}}} + {address_width+1}\'d{size-1};',
           'reg rvw_allowed, rvw_matched;', 'always @* begin rvw_allowed=0; rvw_matched=0;']
    master_width=len(ports[signals['master']]['bits'])
    for region in policy['regions']:
        lo,hi=region['start'],region['end']
        if not (type(lo) is int and type(hi) is int and 0<=lo<hi<=1<<address_width):
            raise ValueError('region bounds must fit the address width')
        permissions=[]
        for rule in region['permissions']:
            master,priv=rule['master'],rule['privilege']
            if not (type(master) is int and 0<=master<1<<master_width and priv in (0,1,3)):
                raise ValueError('invalid master or privilege')
            read,write,execute=[int(rule.get(key,False) is True) for key in ('read','write','execute')]
            permissions.append(f'({signals["master"]} == {master_width}\'d{master} && {signals["privilege"]} == 2\'d{priv} && '
                               f'(!({signals["write"]} && {signals["execute"]})) && ({signals["execute"]} ? 1\'b{execute} : ({signals["write"]} ? 1\'b{write} : 1\'b{read})))')
        touched=f'({addr} < {address_width+1}\'d{hi} && {end} >= {address_width+1}\'d{lo})'
        contained=f'({addr} >= {address_width+1}\'d{lo} && {end} < {address_width+1}\'d{hi})'
        lines += [f'if (!rvw_matched && {touched}) begin rvw_matched=1; rvw_allowed={contained} && ('+(' || '.join(permissions) or "1'b0")+'); end']
    lines += ['end',f'always @(posedge {clock}) if (!{reset} && {signals["request"]} && {signals["grant"]}) assert (rvw_allowed);','endmodule','']
    return '\n'.join(lines)


def run(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = {'schema':'rvw.secure-path/1','status':'inconclusive',
              'limits':'Conservative digital taint only. No physical or whole-core security claim.'}
    started = time.monotonic()
    def budget():
        left = args.timeout - (time.monotonic() - started)
        if left <= 0:
            raise ValueError('total policy proof time limit')
        return left
    try:
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 300:
            raise ValueError('timeout must be in (0,300] seconds')
        check_ident('top', args.top)
        if args.top in ('rvw_secure_path', 'rvw_secure_path__ift'):
            raise ValueError('reserved top name')
        raw = Path(args.rtl).read_bytes()
        if b'`include' in raw or b'$readmem' in raw:
            raise ValueError('self-contained RTL required')
        (out/'dut.v').write_bytes(raw)
        policy = json.loads(Path(args.policy).read_text())
        (out/'policy.json').write_text(json.dumps(policy,indent=2))
        from .pair import proof_settings
        mode, depth, engine = proof_settings(policy)
        result['proof_kind'] = 'bounded' if mode == 'bmc' else 'unbounded'
        result['depth'] = depth if mode == 'bmc' else None
        if policy.get('source_regions'):
            raise ValueError('region-specific source alignment is unsupported')
        if type(policy.get('memory_map', False)) is not bool:
            raise ValueError('memory_map must be Boolean')
        result['policy'] = policy
        result['rtl_sha256'] = hashlib.sha256(raw).hexdigest()
        script = (f'read_verilog dut.v\nhierarchy -check -top {args.top}\nproc\nflatten\n'
                  'check -assert\n' + ('memory_map\n' if policy.get('memory_map') else '') +
                  'techmap\nopt_clean\ncheck -assert\nwrite_json -noscopeinfo mapped.json\n')
        (out/'map.ys').write_text(script)
        tool=shutil.which('yosys')
        if not tool:
            raise ValueError('missing yosys')
        result['mapping_tool']={'path':tool,'sha256':hashlib.sha256(Path(tool).read_bytes()).hexdigest()}
        r=run_group([tool,'-Q','-s','map.ys'],cwd=out,timeout=budget(),capture=True)
        (out/'map.log').write_text((r.stdout or '')+(r.stderr or ''))
        if r.timed_out or r.returncode:
            raise ValueError('RTL mapping failed or timed out')
        design=json.loads((out/'mapped.json').read_text())
        if any(c['type'] in ('$assume','$assert','$cover','$anyseq','$anyconst') for c in design['modules'][args.top]['cells'].values()):
            raise ValueError('DUT properties and nondeterministic cells are unsupported')
        wrapper=out/'secure.v'
        wrapper.write_text((isolation if policy.get("kind") == "isolation" else bind)(design,args.top,policy))
        if policy.get("kind") == "isolation":
            wrapper.write_bytes(raw + b"\n" + wrapper.read_bytes())
        # Run the existing assertion flow. Its captures bind the generated RTL and tools.
        proof_budget = budget()
        argv=[sys.executable,'-m','rvw','formal',mode,'--verilog',str(wrapper),
              '--top','rvw_secure_path','--clock',policy['clock'],'--reset',policy['reset'],
              '--engine',engine,'--depth',str(depth),'--timeout',str(proof_budget),'--out',str(out/'proof'),'--json']
        r=run_group(argv,cwd=out,timeout=proof_budget+5,capture=True)
        (out/'proof.log').write_text((r.stdout or '')+(r.stderr or ''))
        proof_path=out/'proof/result.json'
        if not r.timed_out and proof_path.is_file():
            proof=json.loads(proof_path.read_text())
            result['proof']=proof
            if r.returncode==0 and proof.get('status')=='pass':
                result['status']='pass'
            elif proof.get('status')=='fail' and r.returncode==1:
                result['status']='fail'
        if result['status']=='inconclusive':
            result['reason']='proof did not complete; see proof.log'
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result['reason']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['status']=='pass' else 1
