"""What-if replay of a captured BMC witness. Replay is never a proof."""
from __future__ import annotations

import json
from pathlib import Path

from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group
from rvw.wave import vcd
from . import common


def stimulus(source, target, ports, scope, edits):
    """Replace input values at declared VCD times. Each edit lasts to the next source change."""
    with open(source) as stream:
        header = vcd.read_header(stream)
        variables = {v.name: v for v in header.vars}
        selected = {}
        for port in ports:
            if port['direction'] == 'input':
                name = scope + '.' + port['name']
                if name not in variables:
                    raise ValueError(f'witness lacks input {name}')
                selected[port['name']] = variables[name]
        records = list(vcd.body_records(stream))
    from collections import defaultdict
    grouped = defaultdict(list)
    for time, code, raw in records:
        grouped[time].append((code, raw))
    times = set(grouped)
    replacements = {}
    declared = []
    for edit in edits:
        # PORT@TIME=INTEGER; exact timestamp, decimal or 0x/0b values.
        try:
            lhs, value = edit.split('=')
            name, time = lhs.split('@')
            time, value = int(time), int(value, 0)
            var = selected[name]
        except (ValueError, KeyError):
            raise ValueError(f'invalid input edit {edit!r}; use PORT@TIME=INTEGER') from None
        if time not in times or not 0 <= value < 2 ** var.width:
            raise ValueError(f'edit time or value is out of range: {edit}')
        key = (time, var.code)
        if key in replacements:
            raise ValueError(f'duplicate edit: {edit}')
        replacements[key] = 'b' + format(value, f'0{var.width}b')
        declared.append({'port': name, 'time': time, 'value': value})
    with open(target, 'w') as output:
        output.writelines(header.lines)
        for time in sorted(times):
            output.write(f'#{time}\n')
            for code, raw in grouped[time]:
                if code is not None and (time, code) not in replacements:
                    vcd.write_value(output, raw, code)
            for (t, code), raw in replacements.items():
                if t == time:
                    vcd.write_value(output, raw, code)
    return declared


class ReplayError(ValueError):
    pass


def run(args):
    try:
        with common.sigterm_raises():
            return _run(args)
    except ReplayError as exc:
        out, capture, saved, original = args._cex_context
        result = {'schema': 'rvw.formal.cex/1', 'status': 'inconclusive',
                  'disposition': 'inconclusive', 'error': str(exc),
                  'original_result': str(saved), 'restrictions': original.get('restrictions', []),
                  'requested_edits': args.edit or [], 'input_capture': capture.record()}
        common.write_json(out / 'result.json', result)
        print(json.dumps(result, indent=2) if args.json else 'cex: inconclusive (replay failed)')
        return 1
    except (OSError, ValueError, CaptureError, vcd.WaveError) as exc:
        common.die(str(exc))
    finally:
        common.release(args)


def _run(args):
    source = Path(args.result).resolve()
    if source.is_dir():
        source /= 'result.json'
    root = source.parent
    out = common.check_path('--out', args.out)
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('--out must not overlap the original formal result directory')
    for name in ('hgldd', 'pdg'):
        value = getattr(args, name, None)
        if value and Path(value).resolve().is_relative_to(out):
            raise ValueError(f'--{name} must be outside --out')
    args._rvw_out_lock = common.lock_out(out)
    (out / 'result.json').unlink(missing_ok=True)
    import math
    if not args.timeout > 0 or not math.isfinite(args.timeout):
        raise ValueError('--timeout must be positive')
    # New runs cannot use old optional output or summary files.
    common.clear_outputs(out, 'inputs', 'baseline', 'edited', 'dynpdg.json', 'typed.vcd')
    capture = Capture(out / 'inputs')
    saved = capture.file(source).copy
    original = json.loads(saved.read_text())
    equivalence = original.get('schema') == 'rvw.formal.equiv/1' and original.get('status') == 'not_equivalent'
    if not equivalence and (original.get('schema') != 'rvw.formal/1' or original.get('flow') != 'bmc' or original.get('status') != 'fail'):
        raise ValueError('replay requires a failing BMC or a not_equivalent result')
    traces = original.get('traces', [])
    if not 0 <= args.trace_index < len(traces):
        raise ValueError('--trace-index is out of range')
    original_trace = root / traces[args.trace_index]
    trace = capture.file(original_trace).copy
    if equivalence:
        from .equiv_cex import model_for_trace
        model = capture.file(model_for_trace(root, original_trace)).copy
    else:
        model = capture.file(root / 'sby/model/design.il').copy
    # Preserve the source/check snapshots, the wrapper, and every declared restriction.
    snapshots = [(root, original['input_snapshot'])] if not equivalence else [
        (root / side, row['input_snapshot']) for side, row in zip(('gold','gate'), original['inputs'])]
    for directory, snapshot in snapshots:
        for item in snapshot['files'] + snapshot['artifacts']:
            capture.file(directory / item['path'])
    yosys = capture.tool('yosys')
    converter = capture.tool('vcd2fst', identity_only=True)
    import os
    environment = dict(os.environ)

    args._cex_context = out, capture, saved, original

    def execute(script, directory):
        directory.mkdir(exist_ok=True)
        path = directory / 'replay.ys'
        path.write_text(script)
        with (directory / 'yosys.log').open('w') as log:
            proc = run_group([str(yosys.path), '-Q', '-T', '-s', str(path)],
                             stdout=log, stderr=log, timeout=args.timeout, env=environment)
        if proc.returncode:
            raise ReplayError(f'Yosys replay failed; see {directory / "yosys.log"}')

    # JSON from the captured model determines actual wrapper ports and top.
    metadata = out / 'baseline/model.json'
    execute(f'read_rtlil {model}\nwrite_json {metadata}\n', out / 'baseline')
    modules = json.loads(metadata.read_text())['modules']
    tops = [name for name, module in modules.items() if int(module.get('attributes', {}).get('top', '0'), 2)]
    if len(tops) != 1:
        raise ValueError('captured model has no unique top')
    scope = common.check_ident('captured top', tops[0])
    ports = [dict(name=n, **p) for n, p in modules[scope]['ports'].items()]
    edited = out / 'stimulus.vcd'
    edits = stimulus(trace, edited, ports, scope, args.edit or [])

    def replay(wave, name):
        directory = out / name
        directory.mkdir(exist_ok=True)
        fst = directory / 'stimulus.fst'
        result = run_group([str(converter.path), str(wave), str(fst)], capture=True, timeout=args.timeout)
        if result.returncode:
            raise ValueError('vcd2fst failed')
        execute(f'read_rtlil {model}\nclk2fflogic\nchformal -lower\n'
                f'sim -r {fst} -scope {scope} -timescale 1ns '
                f'-vcd {directory / "wave.vcd"} -fst {directory / "wave.fst"} '
                f'-summary {directory / "summary.json"}\n', directory)
        summary = json.loads((directory / 'summary.json').read_text())
        if (summary.get('version') != 'Yosys sim summary' or not summary.get('steps')
                or not isinstance(summary.get('assertions'), list)
                or any(not isinstance(x, dict) or not {'type', 'path'} <= x.keys()
                       for x in summary.get('assertions', []))):
            raise ValueError('missing simulation evidence')
        return summary

    result = {'schema': 'rvw.formal.cex/1', 'status': 'inconclusive', 'disposition': 'inconclusive',
              'original_result': str(saved), 'restrictions': original.get('restrictions', []),
              'edits': edits, 'note': 'Replay observations are not a proof. Unknown state can hide a failure.'}
    try:
        baseline = replay(trace, 'baseline')
        changed = replay(edited, 'edited')
        result.update(baseline=baseline, edited=changed)
        if equivalence:
            result['source_flow'] = 'equiv'
            result['scope'] = 'failed closed output partition; simulation replay is not a proof'
        properties = {x['property'] for x in original.get('failures', [])}
        failures = [x for x in baseline['assertions'] if x['type'] == '$assert'
                    and (equivalence or scope + '.' + '.'.join(p.lstrip('\\') for p in x['path']) in properties)]
        assumptions = [x for x in changed['assertions'] if x['type'] == '$assume']
        same = [x for x in changed['assertions'] if x['type'] == '$assert'
                and any(x['path'] == f['path'] and x.get('src') == f.get('src') for f in failures)]
        if failures and not assumptions and not any(x['type'] == '$assume' for x in baseline['assertions']):
            result['disposition'] = 'reproduced' if same else 'failure_not_observed'
        result['wave'] = str(out / 'edited/wave.vcd')
        result['fst'] = str(out / 'edited/wave.fst')
        result['navigation'] = navigation(args, capture, out, original)
        if getattr(args, 'minimize', False):
            from .cex_reduce import reduce_trace
            def same_failure(wave, index):
                try:
                    summary = replay(wave, f'reduce-{index}')
                except (ValueError, OSError):
                    return False
                return bool(failures and not any(x['type'] == '$assume' for x in summary['assertions'])
                            and not any(x['type'] == '$assume' for x in baseline['assertions'])
                            and any(x['type'] == '$assert' and any(
                                x['path'] == f['path'] and x.get('src') == f.get('src') for f in failures)
                                for x in summary['assertions']))
            result['reduction'] = reduce_trace(edited, out / 'reduced.vcd', ports, scope,
                                               same_failure, args.max_checks)
        if getattr(args, 'emit_testbench', False):
            from .cex_reduce import testbench
            testbench(edited, out / 'replay_tb.sv', ports, scope)
            execute(f'read_rtlil {model}\nchformal -remove\nwrite_verilog -noattr {out / "replay_model.v"}\n',
                    out / 'export')
            result['testbench'] = {'path': str(out / 'replay_tb.sv'),
                                   'model': str(out / 'replay_model.v'), 'status': 'generated',
                                   'note': 'Stimulus only; formal cells removed. No reproduction verdict.'}
        if getattr(args, 'db', None):
            from rvw.query.db import DesignDB
            from rvw.query.ops import drivers, fanin
            if not args.signal:
                raise ValueError('--db needs --signal for driver analysis')
            db = DesignDB(args.db, capture=capture)
            try:
                result['why'] = {'drivers': drivers(db, args.signal),
                                 'fanin': fanin(db, args.signal, depth=32, limit=2000, include_clock=True),
                                 'staleness': db.staleness(),
                                 'scope': 'Structural candidates; use SpinalTrace for dynamic causes.'}
            finally:
                db.close()
    except (OSError, ValueError) as exc:
        result['error'] = str(exc)
    try:
        capture.verify_tools()
    except CaptureError as exc:
        result['disposition'] = 'inconclusive'
        result['error'] = str(exc)
    result['input_capture'] = capture.record()
    common.write_json(out / 'result.json', result)
    print(json.dumps(result, indent=2) if args.json else f"cex: {result['disposition']} (not a proof)")
    return 1


def navigation(args, capture, out, original):
    """Validate type lookup, compute causes, and optionally launch the viewer."""
    import shutil
    import subprocess
    wave = str(out / 'edited/wave.vcd')
    top = original['top']
    scopes = ['rvw_formal_top', 'dut']
    hgldd = capture.tree(Path(args.hgldd), git=False).copy if args.hgldd else None
    pdg = capture.file(Path(args.pdg)).copy if args.pdg else None
    result = {'status': 'not_requested'}

    def call(name, argv):
        exe = shutil.which(name)
        if exe is None:
            return {'status': 'inconclusive', 'error': f'{name} is not on PATH'}
        tool = capture.tool(exe, identity_only=True)
        command = [str(tool.path), *argv]
        proc = run_group(command, capture=True, timeout=args.timeout)
        (out / (name + '.log')).write_text((proc.stdout or '') + (proc.stderr or ''))
        return {'status': 'completed' if proc.returncode == 0 else 'inconclusive',
                'exit': proc.returncode, 'command': command}

    if hgldd:
        result['types'] = call('spinalwaves-check', ['--vcd', wave, '--hgldd', str(hgldd),
                      '--top-module', top, '--extra-scopes', *scopes,
                      '--out', str(out / 'typed.vcd')])
        result['surfer_command'] = ['surfer-tywaves', wave, '--hgldd-dir', str(hgldd),
                                   '--top-module', top, '--extra-scopes', *scopes]
    if pdg:
        if not args.criterion or args.at_time is None or args.at_time < 0:
            raise ValueError('--pdg needs --criterion and non-negative --at-time in VCD units')
        argv = ['dyn-pdg', '-s', args.criterion, '-p', str(pdg), '-v', str(out / 'baseline/wave.vcd'),
                '--at-time', str(args.at_time), '--top-module', top, '--extra-scopes', *scopes,
                '-o', str(out / 'dynpdg.json'), '--summary']
        if hgldd:
            argv += ['--hgldd-path', str(hgldd)]
        (out / 'dynpdg.json').unlink(missing_ok=True)
        result['causes'] = call('spinaltrace-cli', argv)
        if not (out / 'dynpdg.json').is_file():
            result['causes']['status'] = 'inconclusive'
    if args.open:
        if not hgldd or result['types']['status'] != 'completed':
            result['viewer'] = {'status': 'inconclusive', 'error': 'typed lookup must complete before opening Surfer'}
        elif not shutil.which('surfer-tywaves'):
            result['viewer'] = {'status': 'inconclusive', 'error': 'surfer-tywaves is not on PATH'}
        else:
            # The user explicitly requests a persistent GUI. It outlives the replay job.
            with (out / 'surfer.log').open('w') as log:
                proc = subprocess.Popen(result['surfer_command'], stdout=log, stderr=log, start_new_session=True)
            result['viewer'] = {'status': 'launched', 'pid': proc.pid}
    return result
