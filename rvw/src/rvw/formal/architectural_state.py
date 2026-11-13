"""Observe architectural snapshots in cores without a native RVFI interface."""
import hashlib
import json
import os
from pathlib import Path
import re

from rvw.common.proc import run_group
from .riscv import FIELDS


def monitor(xlen, csrs=()):
    """The project supplies retirement-aligned pre/post state, not guessed latency."""
    widths = dict(retire=1, insn=32, pc_before=xlen, pc_after=xlen,
                  regs_before=xlen*32, regs_after=xlen*32, rs1=5, rs2=5, rd=5,
                  trap=1, intr=1, mode=2, mem_addr=xlen, mem_rmask=xlen//8,
                  mem_wmask=xlen//8, mem_rdata=xlen, mem_wdata=xlen)
    widths.update({f'csr_{name}_{phase}': xlen for name in csrs for phase in ('before','after')})
    ports = [f'input [{width-1}:0] {name}' for name,width in widths.items()]
    rvfi_widths = dict.fromkeys(FIELDS, xlen)
    rvfi_widths.update(valid=1,order=64,insn=32,trap=1,halt=1,intr=1,mode=2,ixl=2,
                      rs1_addr=5,rs2_addr=5,rd_addr=5,mem_rmask=xlen//8,mem_wmask=xlen//8)
    ports += [f'output [{rvfi_widths[f]-1}:0] rvfi_{f}' for f in FIELDS]
    text = ['module rvw_state_monitor(input clock,reset,' + ',\n'.join(ports) + ');',
            'reg [63:0] order = 0;',
            'always @(posedge clock) if(reset) order <= 0; else if(retire) order <= order + 1;']
    values = dict(valid='retire && !reset',order='order',insn='insn',trap='trap',halt='0',intr='intr',
                  mode='mode',ixl='1' if xlen==32 else '2',rs1_addr='rs1',rs2_addr='rs2',
                  rd_addr='trap ? 0 : rd', pc_rdata='pc_before',pc_wdata='pc_after',
                  rs1_rdata=f'rs1 ? regs_before[rs1*{xlen} +: {xlen}] : 0',
                  rs2_rdata=f'rs2 ? regs_before[rs2*{xlen} +: {xlen}] : 0',
                  rd_wdata=f'!trap && rd ? regs_after[rd*{xlen} +: {xlen}] : 0')
    values.update({f:f for f in FIELDS if f.startswith('mem_')})
    text += [f'assign rvfi_{field} = {values[field]};' for field in FIELDS]
    text += ['integer index;', 'always @(posedge clock) if(!reset && retire) begin',
             f'assert(regs_before[0 +: {xlen}] == 0 && regs_after[0 +: {xlen}] == 0);',
             'for(index=1;index<32;index=index+1)',
             f'if(trap || index != rd) assert(regs_before[index*{xlen} +: {xlen}] == regs_after[index*{xlen} +: {xlen}]);',
             'end', 'endmodule']
    return '\n'.join(text)+'\n', widths, rvfi_widths


def generate(manifest, out):
    from .rvfi_binding import ident
    plan = json.loads(Path(manifest).read_text())
    if plan.get('schema') != 'rvw.architectural-state/1':
        raise ValueError('expected rvw.architectural-state/1')
    xlen = plan['xlen']
    if type(xlen) is not int or xlen not in (32,64):
        raise ValueError('XLEN must be 32 or 64')
    csrs = plan.get('csrs', [])
    if not isinstance(csrs,list) or len(set(csrs)) != len(csrs):
        raise ValueError('CSRs must have unique names')
    for name in csrs:
        ident(name)
    text,widths,rvfi_widths = monitor(xlen,csrs)
    signals = plan['signals']
    if set(signals) != set(widths):
        raise ValueError('map every retirement, state and memory signal; no implicit zero observations')
    if len(set(signals.values())) != len(signals):
        raise ValueError('state paths must be distinct named observations')
    for signal in signals.values():
        if not isinstance(signal,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*', signal):
            raise ValueError('state paths need plain dot-separated RTL names')
    top,clock,reset = (ident(plan[k]) for k in ('top','clock','reset'))
    if top in ('rvfi_wrapper','rvw_state_monitor'):
        raise ValueError('top name is reserved by the monitor')
    root = Path(manifest).resolve().parent
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    files, hashes = [], {}
    for i,path in enumerate(plan['verilog']):
        raw = (root/path).read_bytes()
        target = out/f'input_{i}.sv';target.write_bytes(raw)
        files.append(target)
        hashes[path] = hashlib.sha256(raw).hexdigest()
    commands = [f'read_verilog -formal -sv {p.name}' for p in files]
    commands += [f'hierarchy -check -top {top}','proc','flatten','memory_map',f'cd {top}']
    for key,path in signals.items():
        commands += [f'rename {path} rvw_state_{key}', f'expose w:rvw_state_{key}']
    commands += ['cd ..','write_verilog -noattr observed.v','write_json observed.json']
    (out/'observe.ys').write_text('\n'.join(commands)+'\n')
    with (out/'observe.log').open('w') as log:
        process = run_group(['yosys','-Q','-T','-s','observe.ys'],cwd=out,stdout=log,stderr=log,timeout=110)
    if process.returncode or process.timed_out:
        raise ValueError('state exposure failed; see observe.log')
    ports = json.loads((out/'observed.json').read_text())['modules'][top]['ports']
    for key,width in widths.items():
        port = ports.get('rvw_state_'+key,{})
        if port.get('direction') != 'output' or len(port.get('bits',[])) != width:
            raise ValueError('state observation width/direction mismatch: '+key)
    for name in (clock,reset):
        if ports.get(name,{}).get('direction') != 'input' or len(ports[name]['bits']) != 1:
            raise ValueError('clock and reset must be one-bit inputs')
    wrapper = ['module rvfi_wrapper(input clock,reset, `RVFI_OUTPUTS);']
    connections=[]
    for index,(name,port) in enumerate(ports.items()):
        ident(name)
        if port['direction'] not in ('input','output'):
            raise ValueError('inout state interfaces are unsupported')
        if name in (clock,reset):
            local = 'clock' if name==clock else 'reset'
        else:
            local = name if name.startswith('rvw_state_') else f'aux_{index}'
            kind = '(* anyseq *) reg' if port['direction']=='input' else 'wire'
            wrapper.append(f'{kind} [{len(port["bits"])-1}:0] {local};')
        connections.append(f'.{name}({local})')
    wrapper += [f'{top} dut('+','.join(connections)+');']
    connection = ['.clock(clock)','.reset(reset)'] + [f'.{k}(rvw_state_{k})' for k in widths]
    connection += ['@RVFI_CONNECTIONS@']
    wrapper += ['rvw_state_monitor state_monitor('+','.join(connection)+');','endmodule']
    (out/'monitor.sv').write_text(text)
    (out/'wrapper.sv.in').write_text('\n'.join(wrapper)+'\n')
    from .riscv import validate
    cfg = dict(plan['riscv_formal'])
    cfg['root'] = str((root / os.path.expandvars(cfg['root'])).resolve())
    cfg['wrapper'] = str(out/'wrapper.sv.in')
    cfg['verilog'] = [str(out/'observed.v'), str(out/'monitor.sv')]
    cfg['ports'] = {field:'rvfi_'+field for field in FIELDS}
    if cfg.get('nret') != 1 or not cfg['isa'].startswith('rv'+str(xlen)):
        raise ValueError('state monitor needs NRET=1 and matching XLEN')
    validate(cfg)
    lines = ['[core]', 'name = '+json.dumps(plan.get('name', top)), '', '[riscv_formal]']
    lines += [key+' = '+json.dumps(value) for key,value in cfg.items() if key not in ('ports','check_options')]
    lines += ['', '[riscv_formal.ports]']
    lines += [key+' = '+json.dumps(value) for key,value in cfg['ports'].items()]
    for check,settings in cfg.get('check_options',{}).items():
        lines += ['', '[riscv_formal.check_options.'+check+']']
        lines += [key+' = '+json.dumps(value) for key,value in settings.items()]
    (out/'rvw.toml').write_text('\n'.join(lines)+'\n')
    report = dict(schema='rvw.architectural-state-generation/1',status='generated',
                  project=str(out/'rvw.toml'), source_sha256=hashes,manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'monitor.sv',out/'wrapper.sv.in',out/'observed.v')},
                  widths=widths, limits=['One retirement per cycle; snapshots must span that retirement.',
                    'Order is generated; it is not an independent order-conformance observation.',
                    'CSR snapshots are exposed, not interpreted as instruction semantics.',
                    'Bus-to-retirement pairing and environment fairness need project checks.',
                    'No proof or adapter-conformance pass is granted by generation.'])
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main(args):
    try:
        result=generate(args.manifest,args.out)
        print(json.dumps(result) if args.json else str(Path(args.out)/'result.json'))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2
