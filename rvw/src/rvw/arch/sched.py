"""Partial compiler models and retirement-span measurements. No fidelity verdict."""
import json
import os
from pathlib import Path
import re

from rvw.common.proc import run_group
from rvw.regress.config import load_config
from rvw.results import RunResult, write_json
from .core import digest, executable, tool_identity, ROOT


def integer(value, name, low=1, high=4096):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}')
    return value


def fields(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected.split()):
        raise ValueError(f'expected fields: {expected}')


def ident(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*', value):
        raise ValueError('invalid model identifier')
    return value


def description(path):
    d = json.loads(Path(path).read_bytes())
    fields(d, 'schema name config isa entry issue_width buffer_size resources classes mca_cpu')
    if d['schema'] != 'rvw.sched-core/1' or d['isa'] not in ('rv32im', 'rv64im'):
        raise ValueError('unsupported scheduling schema or ISA')
    for k in ('name', 'config'):
        ident(d[k])
    if not isinstance(d['mca_cpu'], str) or not re.fullmatch('[A-Za-z0-9_-]+', d['mca_cpu']):
        raise ValueError('invalid MCA CPU')
    integer(d['entry'], 'entry', 0, 2**32-1)
    if d['entry'] % 4:
        raise ValueError('entry must be word aligned')
    integer(d['issue_width'], 'issue_width', 1, 16)
    integer(d['buffer_size'], 'buffer_size', 0)
    if not isinstance(d['resources'], dict) or not d['resources']:
        raise ValueError('resources must be nonempty')
    for name, count in d['resources'].items():
        ident(name)
        integer(count, 'resource count', 1, 16)
    if not isinstance(d['classes'], list) or not d['classes']:
        raise ValueError('classes must be nonempty')
    names, opcodes, types = set(), set(), set()
    for c in d['classes']:
        fields(c, 'name resource latency occupancy llvm_opcodes gcc_type mnemonic encoding')
        ident(c['name']); ident(c['gcc_type'])
        if c['name'] in names or c['gcc_type'] in types or c['resource'] not in d['resources']:
            raise ValueError('duplicate class/type or unknown resource')
        names.add(c['name']); types.add(c['gcc_type'])
        for k in ('latency', 'occupancy'):
            integer(c[k], k)
        if not isinstance(c['llvm_opcodes'], list) or not c['llvm_opcodes']:
            raise ValueError('empty LLVM opcode mapping')
        for op in c['llvm_opcodes']:
            ident(op)
            if op in opcodes:
                raise ValueError('overlapping LLVM opcode mapping')
            opcodes.add(op)
        # First slice supports three-register integer operations only.
        if c['mnemonic'] not in ('add', 'xor', 'and', 'or', 'mul'):
            raise ValueError('unsupported microkernel mnemonic')
        expected = {'add': 0x33, 'xor': 0x4033, 'and': 0x7033, 'or': 0x6033, 'mul': 0x2000033}
        if c['encoding'] != expected[c['mnemonic']]:
            raise ValueError('encoding does not match mnemonic')
    return d


def render(d):
    name = d['name']
    td = ['include "llvm/Target/Target.td"',
          f'def {name}Model : SchedMachineModel {{',
          f'  let IssueWidth = {d["issue_width"]};',
          f'  let MicroOpBufferSize = {d["buffer_size"]};',
          '  let CompleteModel = 0;', '}', f'let SchedModel = {name}Model in {{']
    md = [';; Partial model. Include only for the selected CPU.',
          f';; TARGET_SCHED_ISSUE_RATE must return {d["issue_width"]}.',
          f'(define_automaton "{name}")']
    slots = '|'.join(f'{name}_issue{i}' for i in range(d['issue_width']))
    units = [f'{name}_issue{i}' for i in range(d['issue_width'])]
    for r, count in d['resources'].items():
        td.append(f'  def {name}Res{r} : ProcResource<{count}>;')
        units.extend(f'{name}_{r}{i}' for i in range(count))
    md.append(f'(define_cpu_unit "{",".join(units)}" "{name}")')
    for c in d['classes']:
        res = f'{name}Res{c["resource"]}'
        td += [f'  def {name}Write{c["name"]} : SchedWriteRes<[{res}]> {{',
               f'    let Latency = {c["latency"]};',
               f'    let ReleaseAtCycles = [{c["occupancy"]}];', '  }',
               f'  def : InstRW<[{name}Write{c["name"]}], (instregex "' +
               '|'.join(f'^{op}$' for op in c['llvm_opcodes']) + '")>;']
        choices = '|'.join(f'({name}_{c["resource"]}{i}*{c["occupancy"]})'
                           for i in range(d['resources'][c['resource']]))
        md += [f'(define_insn_reservation "{name}_{c["name"]}" {c["latency"]}',
               f'  (eq_attr "type" "{c["gcc_type"]}") "({slots})+({choices})")']
    return '\n'.join(td + ['}', '']), '\n'.join(md + [''])


def generate(description_path, out, project=None):
    d = description(description_path)
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    td, md = render(d)
    (out / 'model.td').write_text(td); (out / 'model.md').write_text(md)
    return {'schema': 'rvw.sched-generation/1', 'status': 'reported',
            'description_sha256': digest(Path(description_path).read_bytes()),
            'llvm': str(out / 'model.td'), 'gcc': str(out / 'model.md'),
            'limits': 'Partial target fragments. Neither compiler integration nor accuracy is established.'}


def kernel(c, count, mode):
    lines, words = [], []
    for i in range(count):
        rd = 10 if mode == 'dependent' else 10 + i % 8
        lines.append(f'{c["mnemonic"]} x{rd}, x{rd}, x6')
        words.append(c['encoding'] | rd << 7 | rd << 15 | 6 << 20)
    return lines, words


def assembly(c, count, mode):
    lines, words = kernel(c, count, mode)
    text = ['.option norvc', '.option norelax', '.section .text.init', '.globl _start', '_start:',
            'li x6, 3'] + [f'li x{i}, 1' for i in range(10, 18)] + [
            '.balign 4', '.globl roi_start', 'roi_start:'] + lines + [
            '.globl roi_end', 'roi_end:', 'la x5, tohost', 'li x6, 1', 'sw x6, 0(x5)',
            '1: j 1b', '.section .tohost,"aw",@progbits', '.balign 8', '.globl tohost',
            'tohost: .dword 0', '.globl fromhost', 'fromhost: .dword 0']
    return '\n'.join(text) + '\n', words


def trace_span(raw, header, records, start, words, config, elf_hash):
    parsed = RunResult.from_dict(raw)
    if parsed.why_inconclusive:
        raise ValueError('inconclusive C1 result')
    if (raw.get('schema') != 'rvw.run/1' or raw.get('status') != 'pass' or raw.get('inconclusive')
            or raw.get('elf_sha256') != elf_hash or raw.get('config') != config
            or raw.get('seed') != 1 or raw.get('mem_latency') != 0):
        raise ValueError('C1 pass, identity or fixed timing mismatch')
    if (header.get('schema') not in ('rvw.rvfi/1', 'rvw.rvfi/2')
            or header.get('core') != raw.get('core') or header.get('config') != config):
        raise ValueError('C2 header mismatch')
    if not records or records[-1].get('event') != 'end' or records[-1].get('status') != 'pass':
        raise ValueError('complete passing C2 end required')
    selected = []; last_cycle = -1; order = 0
    for r in records:
        cyc = r.get('cycle')
        if type(cyc) is not int or cyc < last_cycle:
            raise ValueError('nonmonotonic trace cycles')
        last_cycle = cyc
        if r.get('event'):
            if r['event'] in ('trap', 'end') and r is not records[-1]:
                raise ValueError('trap or early end in trace')
            continue
        if r.get('order') != order or any(r.get(k) for k in ('trap', 'intr', 'halt')):
            raise ValueError('incomplete or trapped retirement trace')
        order += 1
        pc = int(r['pc'], 16)
        if start <= pc < start + 4*len(words):
            selected.append(r)
    if len(selected) != len(words):
        raise ValueError('missing or repeated ROI instructions')
    for i, (r, word) in enumerate(zip(selected, words)):
        if int(r['pc'], 16) != start + i*4 or int(r['insn'], 16) != word:
            raise ValueError('ROI instruction mismatch')
    span = selected[-1]['cycle'] - selected[0]['cycle']
    if span <= 0:
        raise ValueError('empty retirement span')
    return span


def slope_report(samples, count):
    a, b = samples
    rtl = (b['rtl_cycles'] - a['rtl_cycles']) / count
    mca = (b['mca_cycles'] - a['mca_cycles']) / count
    if rtl <= 0 or mca <= 0:
        raise ValueError('nonpositive cycle slope')
    return {'rtl_cycles_per_instruction': rtl, 'mca_cycles_per_instruction': mca,
            'error_percent': 100*(mca/rtl-1)}


def command(argv, log, timeout, env=None):
    with Path(log).open('w') as f:
        r = run_group(list(map(str, argv)), stdout=f, stderr=f, timeout=timeout, grace=20, env=env)
    if r.returncode or r.timed_out:
        raise ValueError(f'command failed or timed out; see {log}')


def linker_script(d):
    return (f'ENTRY(_start)\nSECTIONS {{ . = {d["entry"]}; '
            '.text : { *(.text.init) *(.text*) } '
            '. = ALIGN(8); .tohost : { *(.tohost) } }\n')


def measure(description_path, out, project=None, count=32, timeout=600,
            cc='riscv64-unknown-elf-gcc', mca='llvm-mca'):
    d = description(description_path); integer(count, 'count', 16, 256)
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 1800:
        raise ValueError('timeout must be in (0, 1800]')
    config = load_config(project=project)
    if d['config'] not in (config.configs or [config.default_config]):
        raise ValueError('description config is absent from selected project')
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    cc = executable(cc); mca = executable(mca)
    nm = executable(str(Path(cc).with_name(Path(cc).name.replace('gcc', 'nm'))))
    tools = {'cc': tool_identity(cc), 'mca': tool_identity(mca)}
    write_json(out / 'description.json', d)
    linker = out / 'link.ld'
    linker.write_text(linker_script(d))
    jobs, cases = [], []
    for c in d['classes']:
        for mode in ('dependent', 'independent'):
            for n in (count, count*2):
                base = out / f'{c["name"]}-{mode}-{n}'
                source, words = assembly(c, n, mode)
                src = base.with_suffix('.S'); src.write_text(source)
                elf = base.with_suffix('.elf')
                command([cc, '-nostdlib', '-nostartfiles', f'-march={d["isa"]}',
                         '-mabi=' + ('ilp32' if d['isa'].startswith('rv32') else 'lp64'),
                         '-Wl,--no-relax', f'-Wl,-T,{linker}', '-o', elf, src],
                        base.with_suffix('.build.log'), 60)
                symbols = run_group([nm, str(elf)], capture=True, timeout=30)
                if symbols.returncode:
                    raise ValueError('nm failed')
                start = [int(line.split()[0], 16) for line in symbols.stdout.splitlines()
                         if line.split()[-1] == 'roi_start']
                if len(start) != 1:
                    raise ValueError('missing unique ROI symbol')
                snippet = base.with_suffix('.s'); snippet.write_text('\n'.join(kernel(c, n, mode)[0])+'\n')
                log = base.with_suffix('.mca.log')
                command([mca, '-mtriple=' + ('riscv32' if d['isa'].startswith('rv32') else 'riscv64'),
                         '-mcpu=' + d['mca_cpu'], '-iterations=1', snippet], log, 60)
                matches = re.findall(r'^Total Cycles:\s+(\d+)\s*$', log.read_text(), re.M)
                if len(matches) != 1:
                    raise ValueError('MCA total cycles missing')
                run = base.with_suffix('.run')
                jobs.append({'elf': str(elf), 'out': str(run), 'config': d['config'],
                             'seed': 1, 'mem_latency': 0, 'max_cycles': 100000, 'rvfi_trace': True})
                cases.append((c['name'], mode, n, start[0], words, elf, run, int(matches[0])))
    manifest = out / 'jobs.jsonl'
    manifest.write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    env = dict(os.environ)
    if config.source_env:
        env[config.source_env] = str(config.source_repo)
    command([ROOT / 'scripts/with-lock.sh', config.lock or 'arch-rtl', 'nice', '-n', '10',
             *config.adapter, 'run-many', '--manifest', manifest, '--jobs', '1'], out / 'rtl.log', timeout, env=env)
    rows = []
    for name, mode, n, start, words, elf, run, cycles in cases:
        result_path = run / 'result.json'; raw = json.loads(result_path.read_bytes())
        if raw.get('core') != config.name:
            raise ValueError('C1 core mismatch')
        trace_path = run / raw['artifacts']['rvfi_trace']
        records = [json.loads(line) for line in trace_path.read_text().splitlines()]
        span = trace_span(raw, records[0], records[1:], start, words, d['config'], digest(elf.read_bytes()))
        rows.append({'class': name, 'mode': mode, 'count': n, 'rtl_cycles': span, 'mca_cycles': cycles,
                     'elf_sha256': digest(elf.read_bytes()), 'result': str(result_path),
                     'result_sha256': digest(result_path.read_bytes()),
                     'trace': str(trace_path), 'trace_sha256': digest(trace_path.read_bytes())})
    summary = []
    for c in d['classes']:
        for mode in ('dependent', 'independent'):
            samples = [r for r in rows if r['class'] == c['name'] and r['mode'] == mode]
            summary.append({'class': c['name'], 'mode': mode, **slope_report(samples, count)})
    report = {'schema': 'rvw.sched-measure/1', 'status': 'reported', 'model_kind': 'builtin-baseline',
              'generated_model_accuracy': 'inconclusive', 'mca_cpu': d['mca_cpu'], 'tools': tools,
              'description_sha256': digest((out / 'description.json').read_bytes()),
              'samples': rows, 'classes': summary,
              'limits': 'Two-size retirement-span slopes include fetch stalls. No isolated unit latency or compiler-model accuracy claim.'}
    write_json(out / 'report.json', report)
    return report
