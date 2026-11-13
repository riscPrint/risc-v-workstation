"""Bit-blast RTL and a C reference together with native CBMC."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

from rvw.common.proc import run_group
from .bitc import translate


def register(sub):
    p = sub.add_parser('datapath', help='symbolic C reference against mapped RTL with CBMC')
    p.add_argument('--rtl', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--width', type=int, choices=[8, 16, 32, 64], required=True)
    p.add_argument('--latency', type=int, default=0, help='fixed transaction clocks after one reset clock')
    p.add_argument('--unwind', type=int, default=130, help='C loop bound; unwinding assertions are enabled')
    p.add_argument('--case', choices=['all', 'finite', 'nan', 'infinity', 'zero', 'subnormal'], default='all')
    p.add_argument('--rounding', type=int, choices=range(5), default=0)
    p.add_argument('--reference-tree', help='external C dependency tree, such as pinned SoftFloat')
    p.add_argument('--reference-source', action='append', default=[], help='C source relative to reference-tree')
    p.add_argument('--reference-include', action='append', default=[], help='include directory relative to reference-tree')
    p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def case_expression(kind, width):
    if kind == 'all':
        return '1'
    if width not in (16, 32, 64):
        raise ValueError('FP case splitting needs binary16/32/64 width')
    fraction, exponent = {16: (10,5), 32: (23,8), 64: (52,11)}[width]
    e = f'((a >> {fraction}) & {(1<<exponent)-1}ULL)'
    f = f'(a & {(1<<fraction)-1}ULL)'
    return {'finite': f'{e} != {(1<<exponent)-1}', 'nan': f'({e} == {(1<<exponent)-1} && {f} != 0)',
            'infinity': f'({e} == {(1<<exponent)-1} && {f} == 0)',
            'zero': f'({e} == 0 && {f} == 0)', 'subnormal': f'({e} == 0 && {f} != 0)'}[kind]


def run(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(schema='rvw.datapath/1', status='inconclusive', backend='yosys-boolean-cbmc',
                  width=args.width, latency=args.latency, case=args.case, rounding=args.rounding,
                  transaction='inputs held stable; reset one clock; start pulse one clock',
                  scope='one fixed-latency transaction; not a streaming or whole-core proof', inputs={}, tools={})
    def execute(argv, name):
        remaining = args.timeout - (time.monotonic()-started)
        if remaining <= 0:
            raise ValueError('total time limit')
        r = run_group(argv, cwd=out, timeout=remaining, capture=True)
        (out/(name+'.log')).write_text((r.stdout or '')+(r.stderr or ''))
        if r.timed_out:
            raise ValueError(name+' timed out')
        return r
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0 or not 0 <= args.latency <= 256 or args.unwind < 1:
            raise ValueError('positive finite timeout and unwind; latency in 0..256 required')
        for tool in ('yosys', 'cbmc'):
            path = shutil.which(tool)
            if not path:
                raise ValueError('missing tool: '+tool)
            result['tools'][tool] = {'path': path, 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        for src, name in ((args.rtl, 'dut.v'), (args.model, 'reference.c')):
            raw = Path(src).read_bytes()
            (out/name).write_bytes(raw)
            result['inputs'][name] = hashlib.sha256(raw).hexdigest()
            if name == 'dut.v' and (b'`include' in raw or b'$readmem' in raw):
                raise ValueError('self-contained RTL required')
        sources, includes = [], []
        if args.reference_tree:
            root = Path(args.reference_tree).resolve()
            shutil.copytree(root, out/'reference-tree', ignore=shutil.ignore_patterns('.git'))
            result['reference_files'] = {str(p.relative_to(out/'reference-tree')): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in (out/'reference-tree').rglob('*') if p.is_file()}
            for names, target in ((args.reference_source, sources), (args.reference_include, includes)):
                for name in names:
                    path = (out/'reference-tree'/name).resolve()
                    if not path.is_relative_to(out/'reference-tree') or not path.exists():
                        raise ValueError('reference dependency must be inside reference-tree')
                    target.append(str(path))
        elif args.reference_source or args.reference_include:
            raise ValueError('reference-tree is required')
        script = ('read_verilog dut.v\nhierarchy -check -top dut\nproc\nflatten\n'
                  'check -assert\ntechmap\nopt_clean\ncheck -assert\nwrite_json mapped.json\n')
        (out/'map.ys').write_text(script)
        r = execute([result['tools']['yosys']['path'], '-Q', '-s', 'map.ys'], 'yosys')
        if r.returncode:
            raise ValueError('Yosys mapping failed')
        code, ports, put, get = translate(json.loads((out/'mapped.json').read_text()), args.width, args.latency)
        mask = (1 << args.width)-1
        code += '\n#include "reference.c"\n'
        code += '_Static_assert(_Generic(&reference, uint64_t (*)(uint64_t,uint64_t,uint64_t,uint8_t,uint8_t *): 1, default: 0), "reference signature");\n'
        code += 'int main(void) {\nuint64_t a=nondet_u64(), b=nondet_u64(), c=nondet_u64();\n'
        code += f'a &= {mask}ULL; b &= {mask}ULL; c &= {mask}ULL;\n'
        code += f'__CPROVER_assume({case_expression(args.case, args.width)});\n'
        code += f'uint8_t flags=0; uint64_t expected=reference(a,b,c,{args.rounding},&flags);\n'
        code += f'__CPROVER_assert(expected <= {mask}ULL, "reference width");\n'
        code += 'init();\n'
        for name in ('a','b','c','rm'):
            if name in ports:
                code += '\n'.join(put(name, str(args.rounding) if name=='rm' else name))+'\n'
        if args.latency:
            code += '\n'.join(put('reset','1')+put('start','0'))+'\ntick();\n'
            code += '\n'.join(put('reset','0')+put('start','1'))+'\n'
            # Observe completion at the exact declared cycle. Keep operands stable.
            for cycle in range(args.latency):
                code += 'tick();\n'
                if cycle < args.latency-1:
                    code += f'__CPROVER_assert(!{get("done")}, "completion latency");\n'
                if cycle == 0:
                    code += '\n'.join(put('start','0'))+'\n'
            code += f'__CPROVER_assert({get("done")}, "completion latency");\n'
        else:
            code += 'eval();\n'
        code += f'__CPROVER_assert({get("y")} == expected, "datapath result");\n'
        if 'flags' in ports:
            code += f'__CPROVER_assert({get("flags")} == flags, "exception flags");\n'
        code += '}\n'
        (out/'check.c').write_text(code)
        argv = [result['tools']['cbmc']['path'], 'check.c', *sources,
                *[x for p in includes for x in ('-I', p)], '--unwind', str(args.unwind),
                '--unwinding-assertions', '--bounds-check', '--pointer-check', '--div-by-zero-check',
                '--signed-overflow-check', '--undefined-shift-check', '--trace', '--json-ui']
        r = execute(argv, 'cbmc')
        report = json.loads(r.stdout)
        properties = [p for entry in report for p in entry.get('result', [])]
        result['properties'] = properties
        result['solver_exit'] = r.returncode
        # Safety and unwinding failures invalidate the oracle, not the DUT.
        failed = [p for p in properties if p.get('status') == 'FAILURE']
        checks = {'datapath result', 'exception flags', 'completion latency'}
        if r.returncode == 0 and properties and all(p.get('status') == 'SUCCESS' for p in properties):
            if any(p.get('description') == 'datapath result' for p in properties):
                result['status'] = 'proved'
        elif r.returncode == 10 and failed and all(p.get('description') in checks for p in failed):
            result['status'] = 'counterexample'
        else:
            result['reason'] = 'incomplete proof or C safety/unwind failure; see properties and cbmc.log'
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result['reason'] = str(exc)
    result['wall_s'] = round(time.monotonic()-started, 3)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result) if args.json else f'datapath: {result["status"]} ({out})')
    return {'proved': 0, 'counterexample': 1, 'inconclusive': 3}[result['status']]
