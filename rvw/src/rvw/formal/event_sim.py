"""Native timed replay and assertion observations from finite SVA monitors."""
from argparse import Namespace
import json
from pathlib import Path
import re
import time

from rvw.common.proc import run_group
from rvw.results import RunResult
from . import common
from .snapshot import InputSnapshot, digest
from .temporal import lower


def events(data, inputs, clocks):
    if data.get('schema') != 'rvw.formal-events/1':
        raise ValueError('expected rvw.formal-events/1')
    scale = data.get('timescale', '1ns')
    if not re.fullmatch(r'1(s|ms|us|ns|ps|fs)', scale):
        raise ValueError('timescale must be 1<unit>')
    rows, state, last = [], {}, -1
    for entry in data.get('events', []):
        at, changes = entry['time'], entry['inputs']
        if type(at) is not int or at <= last or at < 0:
            raise ValueError('event times must be nonnegative and strictly increasing')
        if set(changes) - set(inputs):
            raise ValueError('event contains an unknown input')
        for name, value in changes.items():
            if not isinstance(value, str) or len(value) != inputs[name] or set(value.lower()) - set('01xz'):
                raise ValueError('input values need exact-width binary four-state strings')
        changed = {name for name, value in changes.items() if state.get(name) != value}
        if last >= 0 and changed & clocks and changed - clocks:
            raise ValueError('data/reset changes must use a separate timestamp from property clock changes')
        state.update(changes)
        if set(state) != set(inputs) or (last < 0 and at != 0):
            raise ValueError('first event must set every input at time zero')
        rows.append((at, dict(changes)))
        last = at
    if not rows:
        raise ValueError('declare at least one event')
    return scale, rows


def testbench(top, ports, observed, scale, rows, raw_pulses=None, state=None, cross_steps=None, unbounded=None, cross=None):
    lines = [f'`timescale {scale}/{scale}', 'module rvw_event_top;']
    inputs = [p for p in ports if p.direction == 'input']
    outputs = [p for p in ports if p.direction == 'output']
    lines += ['reg ' + p.decl() + ';' for p in inputs]
    lines += ['wire ' + p.decl() + ';' for p in outputs]
    prefix='rvw_event_control'
    while any(p.name.startswith(prefix) for p in ports):
        prefix+='_'
    cache={p.name:prefix+'_next'+str(i) for i,p in enumerate(inputs)}
    clocks=sorted({name for row in raw_pulses or [] for name in row}
                  | {name for _,ticks in cross_steps or [] for name in ticks})
    controls=sorted({name for signals,_ in cross_steps or [] for name in signals})
    fire={name:prefix+'_fire'+str(i) for i,name in enumerate(clocks)}
    flags={name:prefix+'_flag'+str(i) for i,name in enumerate(controls)}
    lines += ['reg '+common.Port(cache[p.name],'input',p.width,p.signed).decl()+';' for p in inputs]
    lines += [f'reg {name}=0;' for name in [*fire.values(),*flags.values()]]
    lines += [f'reg {prefix}_drive=0, {prefix}_apply=0, {prefix}_enable=0;',
              f'{top} dut(' + ', '.join(f'.{common.vid(p.name)}({common.vid(p.name)})' for p in ports) + ');']
    # Runtime nonblocking assignments are required here. Verilator converts
    # nonblocking assignments in initial blocks to blocking assignments.
    # Phase one fires monitors. Phase two applies design inputs in a later NBA
    # round. Monitor processes therefore sample the preceding settled values.
    lines += [f'always @({prefix}_drive) if ({prefix}_enable) begin']
    lines += [f'  dut.{name} <= {flags[name]};' for name in controls]
    lines += [f'  if ({fire[name]}) dut.{name} <= 1;' for name in clocks]
    lines += [f'  {prefix}_apply <= !{prefix}_apply;', 'end']
    lines += [f'always @(posedge dut.{name}) dut.{name} <= 0;' for name in clocks]
    lines += [f'always @({prefix}_apply) if ({prefix}_enable) begin']
    lines += [f'  {common.vid(p.name)} <= {cache[p.name]};' for p in inputs]
    lines += ['end', 'initial begin']
    previous = 0
    for index, (at, changes) in enumerate(rows):
        if at > previous:
            lines.append(f'#{at-previous};')
        triggered = list(raw_pulses[index]) if raw_pulses else []
        signals={}
        if cross_steps:
            signals,ticks=cross_steps[index]
            triggered += ticks
        for name in clocks:
            lines.append(f'{fire[name]} = {int(name in triggered)};')
        for name in controls:
            lines.append(f'{flags[name]} = {signals.get(name,0)};')
        for name, value in changes.items():
            lines.append(f"{cache[name]} = {len(value)}'b{value};")
        lines += [f'{prefix}_enable = 1;', f'{prefix}_drive = !{prefix}_drive;']
        if index == 0 and state:
            lines.append('#1;')
            for register in state['registers']:
                signal='.'.join(common.vid(part) for part in register['signal'].split('.'))
                lines.append(f"force dut.{signal} = {register['width']}'b{register['value']};")
            lines.append('#1;')
            for register in state['registers']:
                signal='.'.join(common.vid(part) for part in register['signal'].split('.'))
                lines.append(f'release dut.{signal};')
        for name in observed:
            lines.append(f'$strobe("RVW_OBSERVE {at} {name} %b", {common.vid(name)});')
        previous = at
    lines += ['#1;']
    for prop in unbounded or []:
        prefix=prop['monitor']
        pending=f'dut.{prefix}_pending'+(f' + dut.{prefix}_delayed' if prop['nonoverlap'] else '')
        lines.append(f'$display("RVW_PENDING {prefix} %0d", {pending});')
        if prop.get('disable_iff') is not None:
            lines.append(f'$display("RVW_CANCELLED {prefix} %0d", dut.{prefix}_cancelled);')
    for prop in cross or []:
        prefix = prop['monitor']
        lines.append(f'$display("RVW_PENDING {prefix} %0d", dut.{prefix}_pending);')
        if prop.get('disable_iff') is not None:
            lines.append(f'$display("RVW_CANCELLED {prefix} %0d", dut.{prefix}_cancelled);')
    lines += ['$display("RVW_EVENT_DONE"); $finish;', 'end', 'endmodule']
    return '\n'.join(lines) + '\n'


def counts(output, properties):
    result = {p['monitor']: dict(id=p['id'], kind=p['kind'], passed=0, failed=0, covered=0, missed=0,
                                             activated=0 if p.get('antecedent') is not None else None, source=p.get('source'))
              for p in properties}
    for tag, kind, outcome in re.findall(r'^RVW_SVA (\w+) (assert|assume|cover) (pass|fail|cover|miss)$', output, re.M):
        if tag not in result or kind != result[tag]['kind']:
            raise ValueError('unattributed simulation assertion output')
        field = {'pass': 'passed', 'fail': 'failed', 'cover': 'covered', 'miss': 'missed'}[outcome]
        result[tag][field] += 1
    for tag in re.findall(r'^RVW_ACTIVATE (\w+)$', output, re.M):
        if tag not in result:
            raise ValueError('unattributed antecedent activation')
        result[tag]['activated'] += 1
    for tag,value in re.findall(r'^RVW_PENDING (\w+) (\d+)$',output,re.M):
        if tag not in result:
            raise ValueError('unattributed pending obligation output')
        result[tag]['pending']=int(value)
    for tag,value in re.findall(r'^RVW_CANCELLED (\w+) (\d+)$',output,re.M):
        if tag not in result:
            raise ValueError('unattributed cancellation output')
        result[tag]['cancelled']=int(value)
    return list(result.values())


def run(args):
    with common.sigterm_raises():
        return _run(args)


def _run(args):
    from rvw.common.capture import Capture
    started = time.monotonic()
    out = common.check_path('--out', args.out)
    common.check_ident('top', args.top)
    fd = common.lock_out(out)
    try:
        for path in [args.events, *args.verilog]:
            if Path(path).resolve().is_relative_to((out/'event-inputs').resolve()):
                raise ValueError('replay input is inside the owned event capture; use a different --out')
        common.clear_outputs(out, 'result.json', 'coverage.dat', 'compile.log', 'run.log', 'event-inputs')
        spec_capture = Capture(out / 'event-inputs')
        event_file = spec_capture.file(Path(args.events))
        event_data = json.loads(event_file.copy.read_text())
        snap = InputSnapshot(Namespace(verilog=args.verilog, checks=None, frontend='temporal',
                                       raw_events=True, raw_events_force=event_data.get('state') is not None,
                                       top=args.top), out)
        ports = common.module_ports(snap.sources, args.top, out, args.timeout,
                                    snapshot=snap, allow_async_reset=True)
        if any(p.direction == 'inout' for p in ports):
            raise ValueError('event replay refuses inout ports')
        inputs = {p.name: p.width for p in ports if p.direction == 'input'}
        cross = snap.cross_clock_properties
        bindings = snap.raw_events
        from .raw_events import validate, rewrite, pulses
        validate(bindings, inputs)
        clocks = {p['clock'] for p in snap.temporal_properties} - {b['clock'] for b in bindings} | set(event_data.get('clocks', []))
        clocks |= {p['target_clock'] for p in cross}
        clocks |= {term['signal'] for binding in bindings for term in binding['terms'] if term['edge'] != 'change'}
        if not clocks <= inputs.keys() or any(inputs[c] != 1 for c in clocks):
            raise ValueError('property clocks must be scalar top-level inputs')
        observed = args.observe or [p.name for p in ports if p.direction == 'output']
        if set(observed) - {p.name for p in ports if p.direction == 'output'}:
            raise ValueError('observations must name top-level outputs')
        scale, rows = events(event_data, inputs, clocks)
        from .live_sim import validate_events
        validate_events(rows,snap.unbounded_properties,inputs)
        state = None
        if event_data.get('state') is not None:
            if args.backend != 'icarus':
                raise ValueError('trace state replay requires Icarus four-state semantics')
            from .state_overlay import load
            state = load(event_data['state'], spec_capture, event_file, out, args.top,
                         inputs, rows[0][1], args.timeout)
        if args.backend == 'verilator' and (args.check_x or any(set(v.lower()) & set('xz') for _, row in rows for v in row.values())):
            raise ValueError('four-state replay and --check-x require Icarus')
        original = '\n'.join((out / r['frontend']).read_text() for r in snap.files if r['kind'] == 'source')
        from .live_sim import rewrite as live_rewrite
        original, unbounded = live_rewrite(original,args.top,simulation=True)
        from .cross_clock import rewrite as cross_rewrite, schedule
        original, cross = cross_rewrite(original,args.top,simulation=True)
        original, _ = rewrite(original, args.top, force=state is not None or bool(cross) or bool(unbounded))
        simulation, properties = lower(original, simulation=True)
        properties += cross + unbounded
        model = out / 'simulation.sv'
        model.write_text(simulation)
        bench = out / 'testbench.sv'
        bench.write_text(testbench(args.top, ports, observed, scale, rows, pulses(rows, bindings, inputs), state, schedule(rows,cross,inputs), unbounded, cross))
        snap.seal(model); snap.seal(bench)
        result = RunResult(status='error', config='formal-event-simulation',
                           source={'model_sha256': digest(model)},
                           artifacts={'log': 'run.log', 'coverage': 'coverage.dat'},
                           extra={'inconclusive': 'simulation did not complete'}).to_dict()
        if args.backend == 'icarus':
            compile_cmd = ['iverilog', '-g2012', '-s', 'rvw_event_top', '-o', 'simulation.vvp', model.name, bench.name]
            run_cmd = ['vvp', 'simulation.vvp']
        else:
            compile_cmd = ['verilator', '--binary', '--timing', '-Wno-fatal', '--top-module', 'rvw_event_top',
                           '--Mdir', 'obj', '-o', 'simulation', model.name, bench.name]
            run_cmd = ['./obj/simulation']
        def execute(command, name):
            with (out / name).open('w') as log:
                return run_group(['nice', '-n', '10', *command], cwd=out, stdout=log, stderr=log, timeout=args.timeout)
        compiled = execute(compile_cmd, 'compile.log')
        if compiled.returncode == 0 and not compiled.timed_out:
            completed = execute(run_cmd, 'run.log')
            output = (out / 'run.log').read_text()
            if completed.returncode == 0 and not completed.timed_out and 'RVW_EVENT_DONE' in output:
                observations = [dict(time=int(t), signal=s, value=v) for t,s,v in
                                re.findall(r'^RVW_OBSERVE (\d+) (\w+) ([01xz]+)$', output, re.M)]
                unknowns = [r for r in observations if set(r['value']) & set('xz')]
                if len(observations) != len(rows) * len(observed):
                    raise ValueError('incomplete simulation observation output')
                checks = counts(output, properties)
                failures = sum(p['failed'] for p in checks if p['kind'] == 'assert')
                assumptions = sum(p['failed'] for p in checks if p['kind'] == 'assume')
                attempts = sum(p['passed'] + p['failed'] for p in checks if p['kind'] == 'assert')
                pending=sum(p.get('pending',0) for p in checks if p['kind']=='assert')
                pending_assumptions=sum(p.get('pending',0) for p in checks if p['kind']=='assume')
                if assumptions:
                    reason, status = 'stimulus violates a declared assumption', 'error'
                elif pending_assumptions:
                    reason, status = 'pending unbounded assumptions', 'error'
                elif failures:
                    reason, status = None, 'assert'
                elif args.check_x and unknowns:
                    reason, status = None, 'fail'
                elif pending:
                    reason, status = 'pending unbounded obligations', 'error'
                elif not attempts and not (args.check_x and observations):
                    reason, status = 'no_checks', 'error'
                else:
                    reason, status = None, 'pass'
                result.update(status=status, assertions=checks, unknowns=unknowns,
                              observations=observations, inconclusive=reason or False,
                              scope='finite timestamped simulation; pending future obligations are not discharged')
                coverage = []
                for index, prop in enumerate(checks):
                    if prop['kind'] == 'assume':
                        continue
                    key = f'\x01f\x02simulation.sv\x01l\x021\x01page\x02sva-{prop["kind"]}\x01o\x02{index}:{prop["id"]}'
                    coverage.append(f"C '{key}' {prop['covered'] if prop['kind'] == 'cover' else prop['passed']}")
                (out / 'coverage.dat').write_text('\n'.join(coverage) + '\n')
        result.update(wall_s=time.monotonic()-started, backend=args.backend, x_semantics='four-state' if args.backend == 'icarus' else 'two-state; X not measured',
                      event_capture=spec_capture.record(), tools={'backend': args.backend},
                      state_load=state, property_events=bindings, cross_clock_properties=cross, unbounded_properties=unbounded, raw_event_sampling='settled values before each timestamp input update' if bindings else None)
        snap.finish(result)
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'pass' else 1
    finally:
        import os
        os.close(fd)
