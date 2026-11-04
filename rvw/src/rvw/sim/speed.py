"""Compare paired C1 execution times only after complete C2 equivalence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from rvw.cosim.trace import Trace


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def evidence(path, min_seconds=1.0):
    path = Path(path).resolve()
    raw = path.read_bytes()
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or obj.get('schema') != 'rvw.run/1' or obj.get('status') != 'pass'
            or obj.get('inconclusive') or obj.get('wall_clock_timeout')):
        raise ValueError('speed comparison requires conclusive passing C1')
    seconds = obj.get('details', {}).get('execution_s')
    if not positive(seconds) or seconds < min_seconds:
        raise ValueError('execution_s is missing, invalid or below --min-seconds')
    for key in ('cycles', 'instret'):
        if type(obj.get(key)) is not int or obj[key] <= 0:
            raise ValueError('missing positive C1 counter: ' + key)
    for key in ('elf_sha256', 'rtl_sha256'):
        value = obj.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('missing C1 identity: ' + key)
    native = obj.get('tools', {}).get('native_build', {}).get('sha256')
    if not isinstance(native, str) or len(native) != 64 or any(c not in '0123456789abcdef' for c in native):
        raise ValueError('missing native build identity')
    if type(obj.get('seed')) is not int or not obj.get('core') or not obj.get('config'):
        raise ValueError('missing core, preset or seed')
    details = obj.get('details', {})
    if details.get('concurrent') or details.get('abandoned') or details.get('serial_rerun'):
        raise ValueError('speed samples must be serial first attempts')
    run_id = details.get('simulation_session', {}).get('run_id')
    if not isinstance(run_id, str) or not run_id:
        raise ValueError('missing simulation execution run_id')
    trace_path = Path(obj.get('artifacts', {}).get('rvfi_trace', ''))
    if not trace_path.parts or trace_path.is_absolute() or '..' in trace_path.parts:
        raise ValueError('missing local C2 trace artifact')
    trace_path = path.parent / trace_path
    trace = Trace(trace_path)
    digest = hashlib.sha256()
    count, end, retirements = 0, None, 0
    try:
        header = {k: v for k, v in trace.header.items() if k not in ('source', 'elf', 'seed', 'elf_sha256')}
        for event in trace:
            digest.update(json.dumps(event, sort_keys=True, separators=(',', ':')).encode() + b'\n')
            count += 1
            if 'event' not in event:
                retirements += 1
            if event.get('event') == 'end':
                end = event
    finally:
        trace.close()
    if (end is None or end.get('status') != obj['status'] or end.get('cycle') != obj['cycles']
            or retirements != obj['instret']):
        raise ValueError('C2 is incomplete or differs from C1 terminal counters')
    for key in ('seed', 'elf_sha256', 'core', 'config'):
        if trace.header.get(key) != obj.get(key):
            raise ValueError('C2 header differs from C1: ' + key)
    identity = {k: obj.get(k) for k in ('core', 'config', 'elf_sha256', 'rtl_sha256', 'seed',
                'max_cycles', 'mem_latency', 'irq_schedule', 'elf_load_bias', 'boot_payloads', 'soc_map_sha256')}
    identity.update(model=details.get('model'), header=header, trace=digest.hexdigest(),
                    terminal={k: obj.get(k) for k in ('status', 'cycles', 'instret', 'fail_code')})
    return dict(path=str(path), run_id=run_id, sha256=sha(raw), trace_sha256=sha(trace_path.read_bytes()),
                native_sha256=native, identity=identity, seconds=seconds,
                sim_khz=obj['cycles'] / seconds / 1000,
                sim_instructions_per_s=obj['instret'] / seconds, events=count)


def compare(pairs, *, min_seconds=1.0, resamples=10000, seed=1):
    """Pairs must follow the declared experiment order; native options may differ."""
    if not positive(min_seconds) or type(resamples) is not int or resamples < 1000:
        raise ValueError('use positive min_seconds and at least 1000 bootstrap resamples')
    if len(pairs) < 5:
        raise ValueError('at least five independent pairs are required')
    rows, seen, executions = [], set(), set()
    reference = None
    builds = None
    for baseline, candidate in pairs:
        left, right = evidence(baseline, min_seconds), evidence(candidate, min_seconds)
        for sample in (left, right):
            if sample['path'] in seen or sample['run_id'] in executions:
                raise ValueError('a sample cannot be reused')
            seen.add(sample['path'])
            executions.add(sample['run_id'])
        if left['identity'] != right['identity']:
            raise ValueError('C1 inputs, terminal results or complete C2 events differ')
        current = (left['native_sha256'], right['native_sha256'])
        if builds is not None and builds != current:
            raise ValueError('native build identity changed within a treatment')
        builds = current
        if reference is not None and reference != left['identity']:
            raise ValueError('workload or preset changed across pairs')
        reference = left['identity']
        rows.append(dict(baseline=left, candidate=right, speedup=left['seconds'] / right['seconds']))
    logs = [math.log(row['speedup']) for row in rows]
    rng = random.Random(seed)
    samples = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(resamples))
    interval = [samples[int(.025 * (resamples - 1))], samples[int(.975 * (resamples - 1))]]
    return dict(schema='rvw.sim-speed/1', status='equivalent', core=reference['core'],
                config=reference['config'], pairs=rows, speedup=math.exp(statistics.mean(logs)),
                speedup_ci95=interval, method='paired geometric mean; percentile bootstrap',
                resamples=resamples, bootstrap_seed=seed,
                retain=interval[0] > 1,
                scope='complete trace and terminal equivalence; no ISA oracle claim')


def command(args):
    try:
        report = compare(args.pair, min_seconds=args.min_seconds, resamples=args.resamples, seed=args.seed)
        with args.out.open('x') as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='inconclusive', error=str(exc))))
        return 3
    print(json.dumps(report, allow_nan=False))
    return 0


def sweep(args):
    """Run bounded serial thread experiments through the existing native adapter."""
    import os
    import platform
    import time
    from rvw.common.proc import run_group
    if (args.repeats < 5 or not positive(args.timeout) or args.timeout > 1800
            or not positive(args.min_seconds) or not args.threads or any(n < 1 for n in args.threads)
            or args.max_cycles <= 0 or len(set(args.threads)) != len(args.threads)):
        raise ValueError('use >=5 repeats, unique positive threads, and timeout in (0, 1800]')
    adapter = args.adapter.resolve(strict=True)
    elf = args.elf.resolve(strict=True)
    home = Path(__file__).resolve().parents[4]
    locker = home / 'scripts/with-lock.sh'
    args.out.mkdir(parents=True, exist_ok=False)
    plan = dict(schema='rvw.sim-speed-sweep/1', status='inconclusive',
                host=platform.platform(), logical_cpus=os.cpu_count(),
                adapter=str(adapter), elf=str(elf), elf_sha256=sha(elf.read_bytes()),
                config=args.config, seed=args.seed, repeats=args.repeats,
                threads=args.threads, min_seconds=args.min_seconds,
                timeout_s=args.timeout, order=[], comparisons=[])
    output = args.out / 'sweep.json'

    def publish():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
        temporary.replace(output)

    def run(threads, name):
        out = (args.out / name).resolve()
        env = dict(os.environ)
        # Append one controlled thread option. Refuse an inherited override.
        flags = env.get('SPINAL_VERILATOR_FLAGS', '')
        if '--threads' in flags:
            raise ValueError('remove --threads from inherited SPINAL_VERILATOR_FLAGS')
        env['SPINAL_VERILATOR_FLAGS'] = (flags + f' --threads {threads}').strip()
        record = dict(name=name, threads=threads, flags=env['SPINAL_VERILATOR_FLAGS'], started_unix_s=time.time())
        plan['order'].append(record)
        publish()
        command = [str(locker), args.lock, 'nice', '-n', '10', str(adapter), 'run',
                   '--elf', str(elf), '--out', str(out), '--config', args.config,
                   '--seed', str(args.seed), '--max-cycles', str(args.max_cycles),
                   '--mem-latency', '0', '--rvfi-trace', '--json']
        record['command'] = command
        with (args.out / (name + '.log')).open('w') as log:
            child = run_group(command, env=env, timeout=args.timeout, stdout=log, stderr=log)
        record.update(returncode=child.returncode, timed_out=child.timed_out, ended_unix_s=time.time())
        publish()
        if child.returncode != 0 or child.timed_out:
            raise ValueError('adapter failed or timed out: ' + name)
        return out / 'result.json'

    publish()
    try:
        # Each invocation starts a fresh process. Warm native caches before sampling.
        for n in sorted(set([1, *args.threads])):
            run(n, f'warmup-{n}')
        for n in args.threads:
            paired = []
            for i in range(args.repeats):
                names = [(1, f't{n}-pair{i}-base'), (n, f't{n}-pair{i}-candidate')]
                if i % 2:
                    names.reverse()
                paths = {name: run(t, name) for t, name in names}
                paired.append((paths[f't{n}-pair{i}-base'], paths[f't{n}-pair{i}-candidate']))
            plan['comparisons'].append(compare(paired, min_seconds=args.min_seconds, seed=args.seed))
            publish()
        plan['status'] = 'equivalent'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        plan['error'] = str(exc)
    finally:
        publish()
    print(json.dumps(dict(status=plan['status'], report=str(output))))
    return 0 if plan['status'] == 'equivalent' else 3


def sweep_command(args):
    try:
        return sweep(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='inconclusive', error=str(exc))))
        return 3
