"""Security pair adapter for an existing C1 project, including RV64 cores."""
import argparse
import json
import os
from pathlib import Path
from rvw.cosim.cli import execute_json
from rvw.cosim.platform import Platform
from rvw.results import load_run
from rvw.regress.random_stream import complete
from rvw.sec.common import native
from rvw.sec.core_adapter import compile_elf, reference, render
from rvw.runs.elf import Elf


def qualified(run, comparison):
    return (run.status == "pass" and not run.why_inconclusive
            and complete(comparison, run) and not comparison.get("applied_masks"))


def timing(records, start, end):
    cycles = [int(r['cycle']) for r in records if 'order' in r and start <= int(str(r['pc']), 0) <= end]
    if len(cycles) < 2:
        raise ValueError('security timing window has fewer than two observed retirements')
    return {'cycles': cycles[-1] - cycles[0],
            'retire_cycles': [b-a for a,b in zip(cycles, cycles[1:])]}


def completion_trace(records, tohost):
    """Scope actual retirements to the observed passing tohost store, before drain."""
    prefix = []
    for row in records:
        if row.get('event') == 'end':
            break
        prefix.append(row)
        if ('order' in row and row.get('mem_wmask', 0) and
                int(str(row.get('mem_addr', 0)), 0) == tohost):
            if int(str(row.get('mem_wdata', 0)), 0) & 0xffffffff != 1:
                raise ValueError('security completion store did not report pass')
            prefix.append(dict(event='end', cycle=row['cycle'], status='pass'))
            return prefix
    raise ValueError('passing tohost store was not observed in C2')


def run_case(binding_path, template, request_path, out):
    binding_path = Path(binding_path).resolve()
    binding = json.loads(binding_path.read_text())
    if binding.get('schema') != 'rvw.sec-c1/1':
        raise ValueError('expected rvw.sec-c1/1')
    def path(value):
        p = Path(os.path.expandvars(value))
        return (binding_path.parent / p).resolve()
    binding['_dir'] = binding_path.parent
    binding['platform'] = path(binding['platform'])
    platform = Platform.load(None, binding['platform'])
    binding['march'] = platform.isa
    request = json.loads(Path(request_path).read_text())
    channels = request.get('observations', ['cycles'])
    if set(channels) - {'cycles', 'retire_cycles'}:
        raise ValueError('C1 adapter supports cycles and retire_cycles observations')
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    source = out / 'case.S'
    source.write_text(render(template, request, platform.xlen))
    elf = compile_elf(source, out, binding)
    ref = reference(elf, out, binding)
    native(['nice', '-n', '10', str(path(binding['adapter'])), 'run', '--config', binding['config'],
            '--elf', str(elf), '--out', str(out/'rtl'), '--rvfi-trace', '--mem-latency', '0',
            '--seed', '1', '--max-cycles', '20000', '--json'], out, timeout=120)
    run = load_run(out/'rtl/result.json')
    trace = run.artifact('rvfi_trace')
    comparison = execute_json('check', elf=str(elf), trace=str(trace), platform=str(binding['platform']),
                              core=run.core, strict=True)
    records = [json.loads(line) for line in Path(trace).read_text().splitlines()]
    symbols = Elf(str(elf)).symbols()
    observations = timing(records, symbols['case'].value, symbols['case_end'].value)
    scoped = out/'rtl-completion.jsonl'
    scoped.write_text(''.join(json.dumps(r)+'\n' for r in completion_trace(records, symbols['tohost'].value)))
    response = dict(complete=qualified(run, comparison),
                    reset_complete=True, reference_c2=str(ref), rtl_c2=str(scoped), original_rtl_c2=str(trace),
                    trace_scope="through observed passing tohost store; full trace independently matched first",
                    observations={k: observations[k] for k in channels}, rtl_status=run.status,
                    cycles=run.cycles, core=run.core)
    (out/'comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
    (out/'response.json').write_text(json.dumps(response, indent=2)+'\n')
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', required=True)
    parser.add_argument('--template', required=True)
    parser.add_argument('request'); parser.add_argument('out')
    args = parser.parse_args()
    run_case(args.binding, args.template, args.request, args.out)


if __name__ == '__main__':
    main()
