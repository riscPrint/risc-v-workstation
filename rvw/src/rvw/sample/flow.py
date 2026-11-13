"""Serial sampled RTL flow. Core adapters own bootstrap loading and execution."""
from pathlib import Path
import json

from rvw.common.proc import run_group
from rvw.csim import simpoint, traces
from rvw.cosim.trace import Trace
from rvw.sim.cpu_env import spike_reference
from rvw.sim.spike_bootstrap import capture


def write(path, value):
    path = Path(path)
    temp = path.with_suffix('.partial')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def digest(path):
    return traces.sha256(Path(path))


def reference(spec, work):
    return spike_reference(spec['platform'], spec['elf'], work, spec['shim'])


def profile(spec, work):
    """Stream Spike commits into the existing branch-vector trace format."""
    path = work / 'profile.csim'
    model = reference(spec, work)
    count = 0
    tohost = model.elf.symbols.get('tohost')
    try:
        with path.open('w') as out:
            out.write(traces.HEADER + '\n')
            for count in range(1, spec['instructions'] + 1):
                r = model.step()
                if r['trap'] or r['intr'] or r['halted']:
                    raise ValueError('profile requires trap-free execution for the requested instruction budget')
                insn, pc, nxt = r['insn'], r['pc'], r['pc_next']
                kind = traces.branch_kind(insn, r['rd'], model.platform.xlen)
                if kind:
                    length = 4 if insn & 3 == 3 else 2
                    out.write(f'B {count} {pc:x} {kind} {int(nxt != pc + length)} {nxt:x} {length}\n')
                if tohost is not None and r['mem_wmask'] and r['mem_addr'] == tohost:
                    if r['mem_wdata'] != 1:
                        raise ValueError('workload reported failure through tohost')
                    break
            out.write(f'END {count}\n')
    finally:
        model.close()
    return path


def compare(trace, expected, warmup, length):
    """Reuse the transfer test's normalized architectural field comparisons."""
    parser = Trace(trace)
    actual, ended = [], False
    try:
        if parser.multihart or not parser.state:
            raise ValueError('single-hart state C2 required')
        for r in parser:
            if r.get('event') == 'end':
                ended = r['status'] == 'pass'
            elif 'event' in r or any(r.get(k) for k in ('trap', 'intr', 'halt', 'mem_fault')):
                raise ValueError('unsupported C2 event')
            else:
                actual.append(r)
    finally:
        parser.close()
    if not ended or len(actual) != len(expected) or len(actual) != warmup + length:
        raise ValueError('complete exact-length transfer trace required')
    for i, (rtl, ref) in enumerate(zip(actual, expected)):
        fields = ['pc', 'pc_next', 'insn', 'mode', 'rd', 'mem_rmask', 'mem_wmask']
        fields += ['rd_wdata'] if ref['rd'] else []
        fields += ['mem_addr'] if ref['mem_rmask'] or ref['mem_wmask'] else []
        fields += ['mem_rdata'] if ref['mem_rmask'] else []
        fields += ['mem_wdata'] if ref['mem_wmask'] else []
        for key in fields:
            value = int(rtl[key], 0) if isinstance(rtl[key], str) else rtl[key]
            if value != ref[key]:
                raise ValueError(f'transfer mismatch at {i}: {key}')
    # Retirement-to-retirement span avoids attributing reset/bootstrap cycles to IPC.
    if length < 2:
        raise ValueError('at least two measured retirements required')
    cycles = actual[-1]['cycle'] - actual[warmup]['cycle']
    if cycles <= 0:
        raise ValueError('positive measured cycle span required')
    return dict(status='matched', instructions=length, timed_instructions=length-1,
                cycles=cycles, cpi=cycles/(length-1), ipc=(length-1)/cycles)


def run_point(spec, work, point, warmup):
    work.mkdir(parents=True, exist_ok=True)
    start, length = point['start_instruction'], point['instructions']
    warmup = min(warmup, start)
    model = reference(spec, work)
    try:
        state = capture(model, spec['mapping'], instructions=start-warmup)
        write(work / 'checkpoint.json', state)
        expected = [model.platform.normalize_effect(model.step()) for _ in range(warmup+length)]
        if any(r['trap'] or r['intr'] or r['halted'] for r in expected):
            raise ValueError('unsupported reference suffix')
        write(work / 'expected.json', expected)
    finally:
        model.close()
    request = dict(schema='rvw.sample-request/1', elf=spec['elf'], checkpoint=str(work/'checkpoint.json'),
                   mapping=spec['mapping'], from_reset=(start-warmup == 0), warmup=warmup, instructions=length, timeout=spec['timeout'], out=str(work))
    write(work / 'request.json', request)
    with (work / 'adapter.log').open('w') as log:
        result = run_group(['nice', '-n', '15', *spec['adapter'], str(work/'request.json')],
                           timeout=spec['timeout'], stdout=log, stderr=log)
    if result.timed_out or result.returncode:
        raise ValueError(f'RTL adapter failed: exit {result.returncode}; see {work / "adapter.log"}')
    measured = compare(work/'rvfi.jsonl', expected, warmup, length)
    measured.update(point=point, warmup=warmup, capture=start-warmup,
                    trace_sha256=digest(work/'rvfi.jsonl'), checkpoint_sha256=digest(work/'checkpoint.json'),
                    expected_sha256=digest(work/'expected.json'))
    write(work/'result.json', measured)
    return measured


def aggregate(points):
    good = [p for p in points if p['status'] == 'matched']
    coverage = sum(p['point']['weight'] for p in good)
    cpi = sum(p['point']['weight'] * p['cpi'] for p in good)
    complete = bool(points) and len(good) == len(points) and abs(coverage-1) < 1e-9
    return dict(status='estimated' if complete else 'inconclusive', covered_weight=coverage,
                weighted_ipc=1/cpi if complete and cpi > 0 else None,
                conditional_ipc=coverage/cpi if cpi > 0 else None,
                excluded_points=len(points)-len(good))


def run(manifest, out, interval=10000, max_k=10, warmup=1000, seed=1):
    if min(interval, max_k) < 1 or warmup < 0:
        raise ValueError('positive interval and max_k; nonnegative warmup required')
    manifest = Path(manifest).resolve()
    spec = json.loads(manifest.read_text())
    if spec.get('schema') != 'rvw.sample-study/1':
        raise ValueError('expected rvw.sample-study/1')
    for key in ('elf', 'platform', 'shim', 'mapping'):
        spec[key] = str((manifest.parent / spec[key]).resolve())
    identity = {k: digest(spec[k]) for k in ('elf', 'platform', 'shim', 'mapping')}
    spec['mapping'] = json.loads(Path(spec['mapping']).read_text())
    spec.setdefault('timeout', 120)
    if type(spec['instructions']) is not int or spec['instructions'] < 2:
        raise ValueError('at least two profiled instructions required')
    if not isinstance(spec['adapter'], list) or not spec['adapter']:
        raise ValueError('adapter must be an argv list')
    identity['implementation'] = digest(__file__)
    identity['adapter_files'] = {a: digest(a) for a in spec['adapter'] if Path(a).is_file()}
    identity.update(manifest=digest(manifest), interval=interval, max_k=max_k, warmup=warmup, seed=seed)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    receipt = out/'identity.json'
    if receipt.exists() and json.loads(receipt.read_text()) != identity:
        raise ValueError('resume inputs changed; select a new output directory')
    write(receipt, identity)
    selected = out/'points.json'
    if selected.exists():
        points = json.loads(selected.read_text())
        if digest(out/'profile.csim') != points['sha256']:
            raise ValueError('profile changed during resume')
    else:
        path = profile(spec, out)
        points = simpoint.choose(path, interval, max_k, seed=seed)
        write(selected, points)
    results = []
    for i, point in enumerate(points['points']):
        work = out/f'point-{i:04d}'
        saved = work/'result.json'
        try:
            if saved.exists():
                old = json.loads(saved.read_text())
                if old['trace_sha256'] != digest(work/'rvfi.jsonl') or old['checkpoint_sha256'] != digest(work/'checkpoint.json') or old['expected_sha256'] != digest(work/'expected.json'):
                    raise ValueError('resumed point evidence changed')
                row = dict(compare(work/'rvfi.jsonl', json.loads((work/'expected.json').read_text()),
                                   old['warmup'], point['instructions']), **{k:old[k] for k in
                                   ('point', 'warmup', 'capture', 'trace_sha256', 'checkpoint_sha256', 'expected_sha256')})
            else:
                row = run_point(spec, work, point, warmup)
        except (ValueError, OSError) as exc:
            row = dict(status='excluded', point=point, reason=str(exc))
        results.append(row)
        report = dict(schema='rvw.sample-report/1', **aggregate(results), points=results,
                      identity=identity, confidence='unmeasured; run validation on this core and workload class',
                      weighting='instruction-weighted CPI, then reciprocal; excluded weight is never silently renormalized',
                      timing='N-1 retirement gaps per N-instruction measured interval')
        # A partial progress report cannot claim a complete workload estimate.
        if len(results) != len(points['points']):
            report.update(status='incomplete', weighted_ipc=None)
        write(out/'report.json', report)
    return report
