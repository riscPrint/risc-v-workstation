"""Report recorded native build/run costs without claiming speed qualification."""
from pathlib import Path
import hashlib
import json
import math
import shutil

PROFILES = {
    'default': '',
    'threads-2': '--threads 2',
    'threads-4': '--threads 4',
    'split-10000': '--output-split 10000 --output-split-cfuncs 500',
}


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def report(results=(), *, build_profile='default'):
    if build_profile not in PROFILES:
        raise ValueError('unsupported build profile')
    rows = []
    for path in results:
        path = Path(path).resolve(strict=True)
        raw = path.read_bytes()
        run = json.loads(raw)
        if run.get('schema') != 'rvw.run/1':
            raise ValueError(f'not a C1 result: {path}')
        details = run.get('details', {})
        timing = details.get('model_timing', {})
        execution = _number(details.get('execution_s'))
        cycles, instructions = _number(run.get('cycles')), _number(run.get('instret'))
        rows.append(dict(result=str(path), result_sha256=hashlib.sha256(raw).hexdigest(),
            run_status=run.get('status'), inconclusive=run.get('inconclusive'),
            core=run.get('core'), config=run.get('config'),
            native_build_sha256=run.get('tools', {}).get('native_build', {}).get('sha256'),
            elaboration_s=_number(timing.get('elaboration_s')),
            native_and_setup_s=_number(timing.get('native_and_setup_s')),
            model_compile_s=_number(details.get('model_compile_s')),
            execution_s=execution, scala_compile_s=None, peak_rss_bytes=_number(details.get('child_peak_rss_bytes')),
            peak_rss_scope='maximum child-process build RSS; platform normalized',
            native_probe_profile=details.get('native_profile'),
            cycles=cycles, instructions=instructions,
            sim_khz=cycles / execution / 1000 if execution and cycles is not None else None,
            instructions_per_s=instructions / execution if execution and instructions is not None else None,
            cached=details.get('simulation_session', {}).get('verilator_cached')))
    tools = {}
    for tool in ('verilator', 'iverilog', 'circt-verilog', 'arcilator', 'ccache'):
        path = shutil.which(tool)
        tools[tool] = dict(status='installed' if path else 'not_installed', path=path)
    return dict(schema='rvw.sim-profile/1', status='reported', runs=rows, tools=tools,
        build_profile=build_profile, profile_applied=False, environment={'SPINAL_VERILATOR_FLAGS': PROFILES[build_profile]},
        unsupported=['production Spinal hierarchical bridge access', 'production Spinal captured PGO reuse', 'BOOM Arcilator C1 engine'],
        qualification='none; use complete C2 equivalence and paired speed comparisons',
        tool_check='PATH discovery only; no version, lowering or runtime check')


def command(a):
    try:
        result = report(a.result, build_profile=a.build_profile)
        raw = json.dumps(result, indent=2, allow_nan=False) + '\n'
        if a.out:
            with a.out.open('x') as stream: stream.write(raw)
        print(raw, end='')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps(dict(status='error', message=str(exc))))
        return 2
