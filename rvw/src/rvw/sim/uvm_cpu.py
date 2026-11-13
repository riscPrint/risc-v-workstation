"""Strict native UVM/Spike replay of completed C1 captures."""
from argparse import Namespace
import datetime as dt
import json
import math
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group
from rvw.cosim.inputs import Inputs
from rvw.cosim.elf import Elf
from rvw.cosim.spike import FIELDS, SHIM_VERSION
from rvw.cosim.trace import Trace
from rvw.results import write_json, inconclusive_cause
from rvw.sim import uvm

ROOT = Path(__file__).resolve().parents[4]
COLUMNS = 'pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap mem_fault rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()


def prepare(inputs, out):
    """Bind the C1 result, ELF and complete C2 before emitting DPI records."""
    c1 = inputs.core_run
    elf = Elf(inputs.args.elf)
    p = inputs.platform
    if (not c1 or c1.get('schema') != 'rvw.run/1' or c1.get('status') != 'pass'
            or inconclusive_cause(c1.get('status'), c1, c1.get('signature')) or c1.get('elf_sha256') != uvm.sha(inputs.args.elf)):
        raise ValueError('require passing C1 result bound to the captured ELF')
    if (len(p.ram) != 1 or p.mmio or p.misaligned['load'] != 'trap'
            or p.mode_after_change or elf.xlen != p.xlen):
        raise ValueError('DPI profile requires one RAM, no MMIO, trap misalignment and pre-step mode')
    records = []
    trace = Trace(inputs.args.trace)
    try:
        h = trace.header
        if (h['schema'] != 'rvw.rvfi/1' or trace.multihart or not trace.state
                or h['xlen'] != p.xlen or h['isa'].lower() != p.isa.lower()
                or h['core'] != c1.get('core') or h['config'] != c1.get('config')):
            raise ValueError('unsupported or inconsistent C1/C2 profile')
        ended = False
        for row in trace:
            if 'event' in row:
                if row['event'] == 'end' and row['status'] == 'pass':
                    ended = True
                elif row['event'] == 'irq' and not row['levels']:
                    continue
                else:
                    raise ValueError('DPI profile does not support trap/IRQ/reset events')
                continue
            if row.get('fault_access') or row.get('csr_state') or row['intr'] or row['halt']:
                raise ValueError('extended observation requires another DPI profile')
            if row['order'] != len(records):
                raise ValueError('DPI capture must start at order zero with no gaps')
            records.append(row)
        if not ended or not records:
            raise ValueError('require a nonempty complete passing C2 trace')
    finally:
        trace.close()
    if c1.get('instret') != len(records):
        raise ValueError('C1 retirement count differs from C2')
    (out / 'records.txt').write_text(str(len(records)) + '\n' + ''.join(
        ' '.join(f'{int(row[k]):x}' for k in COLUMNS) + '\n' for row in records))
    base, size = p.ram[0]
    with (out / 'image.txt').open('w') as image:
        for address, data, memsz in elf.segments:
            if address < base or address + memsz > base + size:
                raise ValueError('ELF outside configured RAM')
            # Shim pages start at zero. This includes ELF zero-fill bytes.
            for i, value in enumerate(data):
                image.write(f'{address+i:x} {value:x}\n')
    def sv_string(value):
        return json.dumps(str(value))
    shim = inputs.shim
    init = [sv_string(shim['library']['copy']), sv_string(shim['source']['sha256']),
            sv_string(shim['manifest_data']['build_id']), sv_string(p.reference_isa or p.isa),
            sv_string(p.privilege_modes), str(p.xlen), str(p.pmp_regions),
            str(int(p.absent_pmp_csrs != 'trap')), str(int(p.aligned_mem)),
            f"64'h{base:x}", f"64'h{size:x}", f"64'h{p.reset_pc:x}", sv_string(out / 'image.txt'), str(p.pmp_granularity)]
    (out / 'cpu_top.svh').write_text('''module top;
 import uvm_pkg::*; import cpu_vip::*;
 import "DPI-C" function int rvw_uvm_init(input string lib, source_hash, build_hash,
 input string isa, modes, input int unsigned bits, pmp, input int absent_zero, align,
 input longint unsigned base, size, pc, input string image, input longint unsigned grain);
 import "DPI-C" function void rvw_uvm_close();
 initial begin
  if(rvw_uvm_init(''' + ','.join(init) + ''')!=0) $fatal(1,"Spike init: %s",rvw_uvm_error());
  run_test("cpu_test"); rvw_uvm_close();
 end
 initial begin #10000000; $fatal(1,"watchdog"); end
endmodule
''')
    if SHIM_VERSION != 8:
        raise ValueError('update the native DPI ABI profile')
    (out / 'spike_effect.h').write_text('#include <cstdint>\nstruct Effect {\n' + ''.join(
        f' uint64_t {name};\n' for name in FIELDS) + ' uint64_t regs[32]; char disasm[256];\n};\n')
    return records


def validate_request(c1, *, config, seed, max_cycles):
    for name, expected in (('config',config),('seed',seed),('max_cycles',max_cycles)):
        actual = c1.get(name)
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError(f'C1 {name} does not match the requested option')


def run(out, *, run_dir=None, elf, platform, archive, verilator='verilator', timeout=600,
        adapter=None, config=None, lock=None, seed=1, max_cycles=200000):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if bool(run_dir) == bool(adapter):
        raise ValueError('select exactly one of run_dir or adapter')
    if adapter and (not config or not lock or type(seed) is not int or seed < 1
                    or type(max_cycles) is not int or max_cycles < 1):
        raise ValueError('adapter requires config, lock, positive seed and max_cycles')
    executable = shutil.which(verilator)
    if not executable:
        raise ValueError('Verilator is not installed')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    adapter_command = None
    if adapter:
        run_dir = out / 'c1'
        adapter_command = [str(Path(adapter).resolve()), 'run', '--elf', str(Path(elf).resolve()),
                           '--out', str(run_dir), '--config', config, '--seed', str(seed),
                           '--max-cycles', str(max_cycles), '--rvfi-trace', '--json']
        with (out / 'adapter.log').open('w') as log:
            result = run_group(adapter_command, timeout=timeout, stdout=log, stderr=log)
        if result.returncode or result.timed_out:
            raise ValueError('C1 adapter failed or timed out; see adapter.log')
    c1 = json.loads((Path(run_dir) / 'result.json').read_text())
    if adapter:
        validate_request(c1, config=config, seed=seed, max_cycles=max_cycles)
    trace_name = c1.get('artifacts', {}).get('rvfi_trace')
    if not isinstance(trace_name, str):
        raise ValueError('C1 has no RVFI artifact')
    trace = (Path(run_dir) / trace_name).resolve()
    if not trace.is_relative_to(Path(run_dir).resolve()):
        raise ValueError('C1 trace must be inside the run directory')
    args = Namespace(core=c1.get('core'), platform=Path(platform), elf=Path(elf),
                     trace=trace, cosim_action='check', model='spike', history=10,
                     strict=True, strict_sync=(), timeout=timeout)
    inputs = Inputs(args, out)
    # Inputs captures result.json beside the trace. Require the original C1 artifact layout.
    if inputs.core_run != c1:
        raise ValueError('C1 result must be beside its trace')
    records = prepare(inputs, out)
    sources = [ROOT / 'Uvm/tests/cpu.sv', ROOT / 'Uvm/spike_bridge.cpp']
    hashes = {str(path): uvm.sha(path) for path in sources}
    rows, commands = [], [adapter_command] if adapter_command else []
    version = run_group([executable, '--version'],capture=True,timeout=10)
    if version.returncode or version.timed_out:
        raise ValueError('cannot identify Verilator')
    def execute(command, **kwargs):
        if lock:
            command = [str(ROOT/'scripts/with-lock.sh'),lock,'nice','-n','10',*command]
        return run_group(command, **kwargs)
    try:
        library = uvm.unpack(Path(archive), out / 'library')
        command = [executable, '--binary', '--timing', '--assert', '-Wno-fatal', '-j', '2',
                   '--top-module', 'top', '+define+UVM_NO_DPI', f'+incdir+{library / "src"}',
                   f'+incdir+{out}', str(library / 'src/uvm_pkg.sv'), *map(str, sources),
                   '-CFLAGS', f'-I{out}', '--Mdir', str(out / 'build')]
        commands.append(command)
        with (out / 'build.log').open('w') as log:
            result = execute(command, timeout=timeout, stdout=log, stderr=log)
        if result.returncode or result.timed_out:
            raise ValueError('DPI build failed; see build.log')
        for negative in (False, True):
            name = 'fault' if negative else 'normal'
            command = [str(out / 'build/Vtop'), f'+records={out / "records.txt"}']
            if negative:
                command.append('+corrupt')
            commands.append(command)
            with (out / f'{name}.log').open('w') as log:
                result = execute(command, timeout=timeout, stdout=log, stderr=log, cwd=out)
            text = (out / f'{name}.log').read_text()
            good = not result.timed_out and (
                result.returncode != 0 and '[SPIKE_MISMATCH]' in text and 'RVW_CPU_DONE' not in text
                if negative else result.returncode == 0 and text.count('RVW_CPU_DONE') == 1
                and re.findall(r'^RVW_CPU_CHECKED (\d+)$', text, re.M) == [str(len(records))]
                and not re.search(r'^UVM_(?:ERROR|FATAL)\b(?!\s*:\s*0\s*$)',text,re.M))
            rows.append(dict(id='spike_fault_detection' if negative else 'spike_retirements',
                             seed=c1.get('seed', 1), kind='uvm', status='pass' if good else 'error',
                             simulator_exit=result.returncode, wall_clock_timeout=result.timed_out,
                             signature=None if good else 'uvm:cpu-incomplete',
                             **({} if good else {'inconclusive': 'missing CPU conformance evidence'}),
                             artifacts={'log': f'{name}.log'}))
    except (OSError, ValueError) as exc:
        rows.append(dict(id='build', seed=1, kind='uvm',status='error',
                         signature='uvm:cpu-build', inconclusive=str(exc)))
    if any(uvm.sha(Path(p)) != digest for p, digest in hashes.items()):
        for row in rows:
            row.update(status='error', signature='uvm:source-changed',
                       inconclusive='DPI sources changed during run')
    inputs.capture.verify_tools()
    report = dict(schema='rvw.results/1', suite='uvm-cpu-replay', core=c1['core'],
                  config=c1['config'], run_id=out.name, tests=rows, commands=commands,
                  created=dt.datetime.now(dt.timezone.utc).isoformat(),
                  checked_instructions=len(records), source={'identity_complete': False,
                  'input_sha256': hashes}, reproduction=inputs.metadata(),
                  profile='scalar-c2-v1-strict-no-irq', mode='offline-c1-replay',
                  verilator=version.stdout.strip(), uvm_commit=uvm.COMMIT,
                  uvm_archive_sha256=uvm.ARCHIVE_SHA256)
    write_json(out / 'results.json', report)
    return report


def register(sub):
    parser = sub.add_parser('uvm-cpu', help='check a complete C1 capture with native UVM and Spike DPI')
    for name in ('out','elf','platform','archive'):
        parser.add_argument('--'+name,type=Path,required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--run-dir',type=Path)
    source.add_argument('--adapter',type=Path)
    parser.add_argument('--config')
    parser.add_argument('--lock',help='machine lock for native DPI compilation and replay')
    parser.add_argument('--seed',type=int,default=1)
    parser.add_argument('--max-cycles',type=int,default=200000)
    parser.add_argument('--verilator',default='verilator')
    parser.add_argument('--timeout',type=float,default=600)
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=command)


def command(args):
    import sys
    try:
        report = run(args.out, run_dir=args.run_dir, elf=args.elf, platform=args.platform,
                     archive=args.archive, verilator=args.verilator, timeout=args.timeout,
                     adapter=args.adapter, config=args.config, lock=args.lock,
                     seed=args.seed, max_cycles=args.max_cycles)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report) if args.json else str(args.out / 'results.json'))
    return 0 if report['tests'] and all(r['status']=='pass' for r in report['tests']) else 2
