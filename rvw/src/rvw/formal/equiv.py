"""Conservative sequential equivalence for two captured RTL revisions."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from types import SimpleNamespace

from . import common
from .flows import _inputs


def register(sub):
    p = sub.add_parser('equiv', help='prove sequential equivalence of two RTL revisions')
    p.add_argument('--memory-map', action='store_true', help='lower finite memories exactly to registers; requires unmatched-state prove')
    p.add_argument('--sampled-events', action='store_true', help='conditional global-sample clock-event comparison')
    p.add_argument('--stable-at-edge', action='append', default=[], metavar='INPUT', help='input stable across sampled root rising edges')
    p.add_argument('--state-encoding', help='JSON finite register encoding relations; checked without assumptions')
    p.add_argument('--blackbox-contract', help='explicit trusted behavioral models; result remains conditional')
    p.add_argument('--gold', nargs='+', help='reference RTL files')
    p.add_argument('--gate', nargs='+', help='changed RTL files')
    p.add_argument('--gold-rev')
    p.add_argument('--gate-rev')
    p.add_argument('--config', help='project generator configuration')
    p.add_argument('--top', required=True)
    p.add_argument('--clock', default='clk')
    p.add_argument('--reset', help='shared synchronous reset port, driven by the harness')
    p.add_argument('--reset-active', choices=['high', 'low'], default='high')
    p.add_argument('--reset-cycles', type=int, default=1)
    p.add_argument('--settle', type=int, default=0, help='unchecked clocks after reset (explicit latency assumption)')
    p.add_argument('--dsec', action='store_true', help='also run ABC dsec as an advisory check')
    p.add_argument('--pair', action='append', default=[], metavar='GOLD=GATE',
                   help='pair flattened register names; widths must agree')
    p.add_argument('--latency', type=int, default=0,
                   help='candidate output lags reference by this many clocks (0..64)')
    p.add_argument('--latency-map', action='append', default=[], metavar='OUTPUT=CYCLES',
                   help='override output lag in -64..64; negative means reference lags')
    p.add_argument('--output-map', action='append', default=[], metavar='GOLD=GATE',
                   help='rename candidate outputs at the comparison boundary')
    p.add_argument('--unmatched-state', choices=['refuse', 'prove'], default='refuse',
                   help='prove all internal state without name pairing; no state equality assumptions')
    p.add_argument('--timeout', type=float, default=60, help='total proof budget in seconds')
    p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def state(body, *, include_latches=False):
    """Cover every register Q bit with a stable user-visible net name."""
    qbits = set()
    for cell in body['cells'].values():
        if cell['type'] in common._SYNCHRONOUS_STATE or (include_latches and cell['type']=='$dlatch'):
            qbits.update(cell['connections']['Q'])
        elif not cell['type'].startswith('$'):
            raise ValueError('blackbox or unresolved module obligations are not supported')
        elif cell['type'].startswith('$mem'):
            raise ValueError('memory state mapping is not supported')
        elif cell['type'] in ('$assert', '$assume', '$cover', '$check', '$initstate', '$anyseq', '$anyconst'):
            raise ValueError('design properties and nondeterministic cells are not supported')
    names = {}
    covered = set()
    for name, net in sorted(body['netnames'].items(), key=lambda kv: (kv[1].get('hide_name', 0), kv[0])):
        bits = tuple(net['bits'])
        if bits and set(bits) <= qbits and set(bits) - covered and not name.startswith('$'):
            common.check_hier('register', name)
            names[name] = bits
            covered.update(bits)
    if qbits - covered:
        raise ValueError('register bits have no stable name')
    return names


def mapping(gold, gate, pairs):
    result, used = [], set()
    explicit = {}
    for pair in pairs:
        a, sep, b = pair.partition('=')
        if not sep or a in explicit or b in used:
            raise ValueError('pairs must be unique GOLD=GATE names')
        common.check_hier('--pair', a)
        common.check_hier('--pair', b)
        explicit[a] = b
        used.add(b)
    used.clear()
    for a, bits in gold.items():
        b = explicit.get(a, a)
        if a not in explicit and b in explicit.values():
            continue
        if b in gate and len(bits) == len(gate[b]) and b not in used:
            result.append({'gold': a, 'gate': b, 'width': len(bits),
                           'method': 'manual' if a in explicit else 'name'})
            used.add(b)
    from .register_match import suggest
    result.extend(suggest(gold, gate, result))
    used.update(row['gate'] for row in result)
    missing = {'gold': sorted(set(gold) - {r['gold'] for r in result}),
               'gate': sorted(set(gate) - used)}
    if set(explicit) - set(gold) or set(explicit.values()) - set(gate):
        raise ValueError('manual pair names must identify registers')
    return result, missing


def output_contract(ports, latency, entries, renames):
    outputs = {p.name for p in ports if p.direction == 'output'}
    delays = {name: latency for name in outputs}
    aliases = {}
    for rows, target, numeric in ((entries, delays, True), (renames, aliases, False)):
        seen = set()
        for row in rows:
            name, sep, value = row.partition('=')
            if not sep or name not in outputs or name in seen:
                raise ValueError('output mappings require distinct declared OUTPUT=VALUE entries')
            seen.add(name)
            if numeric:
                value = int(value)
                if not -64 <= value <= 64:
                    raise ValueError('output latency must be in -64..64')
            else:
                common.check_ident('candidate output', value)
            target[name] = value
    names = [aliases.get(name, name) for name in outputs]
    if len(set(names)) != len(names):
        raise ValueError('output mapping must be one-to-one')
    return delays, aliases


def harness(args, ports, *, delay=0, delays=None, aliases=None, encoding=None):
    delays = delays or {}
    aliases = aliases or {}
    decl, connect, assigns = [], [], []
    for p in ports:
        if p.name == args.reset:
            connect.append(f'.{p.name}(rvw_reset)')
            continue
        decl.append(f'{p.direction} {p.decl()}')
        if p.direction == 'output':
            assigns.append(f'wire [{p.width-1}:0] rvw_raw_{p.name};')
            observed = f'rvw_raw_{p.name}'
            for index in range(delays.get(p.name, delay)):
                stage = f'rvw_delay_{p.name}_{index}'
                assigns.append(f'reg [{p.width-1}:0] {stage};')
                assigns.append(f'always @(posedge {args.clock}) {stage} <= {observed};')
                observed = stage
            assigns.append(f'assign {p.name} = rvw_ready ? {observed} : {p.width}\'b0;')
            connect.append(f'.{aliases.get(p.name, p.name)}(rvw_raw_{p.name})')
        else:
            connect.append(f'.{p.name}({p.name})')
    if encoding:
        from .state_encoding import harness as encoding_harness
        extra_decl, extra_connect, extra_assign = encoding_harness(*encoding)
        decl.extend(extra_decl); connect.extend(extra_connect); assigns.extend(extra_assign)
    limit = (args.reset_cycles if args.reset else 0) + args.settle + getattr(args, "_max_latency", args.latency)
    if limit:
        width = max(1, limit.bit_length())
        control = (f'reg [{width-1}:0] rvw_count = 0;\n'
                   f'always @(posedge {args.clock}) if (rvw_count < {limit}) rvw_count <= rvw_count + 1;\n'
                   f'wire rvw_ready = rvw_count == {limit};\n')
        if args.reset:
            control += f'wire rvw_reset = {"" if args.reset_active == "high" else "!"}(rvw_count < {args.reset_cycles});\n'
    else:
        control = 'wire rvw_ready = 1;\n'
    if getattr(args, 'sampled_events', False):
        from .event_equiv import constraints
        assigns.extend(constraints(args, ports))
    return (f'module rvw_equiv({", ".join(decl)});\n' + control + '\n'.join(assigns)
            + f'\n{args.top} dut({", ".join(connect)});\nendmodule\n')


def verdict(rc, timed_out, partitions, unmatched, traces):
    if timed_out or any(unmatched.values()) or not partitions:
        return 'inconclusive'
    if rc == 0 and all(p['status'] == 'PASS' for p in partitions):
        return 'equivalent'
    if any(p['status'] == 'FAIL' for p in partitions) and traces:
        return 'not_equivalent'
    return 'inconclusive'


def run(args):
    with common.sigterm_raises():
        try:
            return _run(args)
        finally:
            common.release(args)


def _run(args):
    from rvw.common.capture import CaptureError
    out = common.check_path('--out', args.out)
    args._rvw_out_lock = common.lock_out(out)
    common._remove_result(out)
    started = time.monotonic()
    from .tools import ACTIVE
    token = ACTIVE.set(None)
    snapshots = []
    result = {'schema': 'rvw.formal.equiv/1', 'status': 'inconclusive', 'top': args.top,
              'partitions': [], 'traces': [], 'state_mapping': [], 'unmatched': {},
              'restrictions': {'clock': args.clock, 'reset': args.reset,
                               'reset_active': args.reset_active, 'reset_cycles': args.reset_cycles, 'settle': args.settle,
                               'latency': args.latency, 'unmatched_state': args.unmatched_state, 'blackboxes': 'refused', 'state_model': 'two-state'}}
    def budget():
        left = args.timeout - (time.monotonic() - started)
        if left <= 0:
            raise TimeoutError('total time limit')
        return left
    try:
        common.check_ident('--top', args.top)
        if args.top == 'rvw_equiv':
            raise ValueError('rvw_equiv is reserved for the proof wrapper')
        common.check_ident('--clock', args.clock)
        if args.reset:
            common.check_ident('--reset', args.reset)
            if args.reset == args.clock:
                raise ValueError('clock and reset must be different inputs')
        if not math.isfinite(args.timeout) or args.timeout <= 0 or args.reset_cycles < 1 or args.settle < 0:
            common.die('timeout must be finite and positive; reset-cycles must be positive')
        if not 0 <= args.latency <= 64:
            raise ValueError('latency must be in 0..64')
        memory_map = getattr(args, 'memory_map', False)
        if memory_map and args.unmatched_state != 'prove':
            raise ValueError('memory-map requires unmatched-state prove')
        sampled = getattr(args, 'sampled_events', False)
        stable = getattr(args, 'stable_at_edge', [])
        if stable and not sampled:
            raise ValueError('stable-at-edge requires sampled-events')
        if sampled:
            if args.unmatched_state != 'prove' or args.dsec:
                raise ValueError('sampled-events requires unmatched-state prove and excludes advisory dsec')
            result['event_model'] = {'backend':'yosys clk2fflogic', 'scope':'global input samples; no between-sample event claim', 'stable_at_edge':stable}
        revisions = (args.gold_rev, args.gate_rev)
        if any(revisions):
            if not all(revisions) or args.gold or args.gate:
                raise ValueError('give both revisions, without --gold or --gate RTL')
            from .export import export_revision
            # Export directories must be new. Retain failed exports for diagnosis.
            for side, revision in zip(('gold', 'gate'), revisions):
                rtl, record = export_revision(getattr(args, 'project', None), revision,
                    args.config, args.top, out / (side + '-export'), budget())
                setattr(args, side, [str(rtl)])
                result.setdefault('exports', {})[side] = record
        if not args.gold or not args.gate:
            raise ValueError('give --gold/--gate RTL or --gold-rev/--gate-rev')
        if getattr(args, 'blackbox_contract', None):
            from .blackbox_models import load
            models, record = load(args.blackbox_contract, out)
            args.gold = [*args.gold, *models]
            args.gate = [*args.gate, *models]
            result['blackbox_contract'] = record
            result['restrictions']['blackboxes'] = 'trusted conditional behavioral models'
        for source in args.gold + args.gate:
            if not any(revisions) and Path(source).resolve().is_relative_to(out):
                raise ValueError('RTL inputs must be outside --out')
        common.clear_outputs(out, 'gold', 'gate', 'eqy', 'equiv.eqy', 'eqy.log')
        encoding_rows = []
        if getattr(args, 'state_encoding', None):
            from . import state_encoding
            encoding_rows, result['encoding_contract'] = state_encoding.load(args.state_encoding, out)
            result['encoding_verdict'] = 'not_proved'
            if args.dsec:
                raise ValueError('state-encoding excludes advisory dsec')
        bodies, portsets, proof_models = [], [], []
        delays, aliases = {}, {}
        for side in ('gold', 'gate'):
            directory = out / side
            directory.mkdir()
            a = SimpleNamespace(**vars(args))
            a.verilog, a.checks, a.engine = getattr(args, side), None, 'abc:pdr'
            a.timeout = budget()
            snapshot, ports, models = _inputs(a, directory, ['SYNTHESIS'], allow_latches=sampled)
            snapshots.append(snapshot)
            # Each side owns its active tool context until the command ends.
            if not sampled:
                common.probe_clocks(models, args.top, args.clock, directory, budget())
            if memory_map:
                from .equiv_memory import lower
                model, record = lower(models[0], args.top, directory, snapshot, budget)
                models = [model]
                result.setdefault('memory_mapping', {})[side] = record
            script = (f'read_rtlil {models[0]}\nhierarchy -check -top {args.top}\nflatten\n'
                      f'write_json {directory / "flat.json"}\n')
            (directory / 'flat.ys').write_text(script)
            rc, _ = common.run(['yosys', '-Q', '-s', 'flat.ys'], directory, directory / 'flat.log', budget())
            if rc:
                raise ValueError('flattening failed')
            flat = json.loads((directory / 'flat.json').read_text())
            body = flat['modules'][args.top]
            bodies.append(state(body, include_latches=sampled))
            proof_models.append(state_encoding.expose(encoding_rows, side, flat, bodies[-1], args.top, directory, budget, snapshot)
                                if encoding_rows else models[0])
            for p in ports:
                common.check_ident('port', p.name)
                if p.name.startswith('rvw_'):
                    raise ValueError('port names with rvw_ are reserved for the proof wrapper')
                if p.direction == 'inout':
                    raise ValueError('inout ports are unsupported')
            if not any(p.name == args.clock and p.direction == 'input' and p.width == 1 for p in ports):
                raise ValueError('clock must be a one-bit input on both designs')
            if not any(p.direction == 'output' for p in ports):
                raise ValueError('no output obligations')
            if args.reset and not any(p.name == args.reset and p.direction == 'input' and p.width == 1 for p in ports):
                raise ValueError('reset must be a one-bit input on both designs')
            if side == 'gold':
                delays, aliases = output_contract(ports, args.latency,
                    getattr(args, 'latency_map', []), getattr(args, 'output_map', []))
                args._max_latency = max(abs(v) for v in delays.values())
                result['output_mapping'] = aliases
                result['restrictions']['latency_map'] = delays
            else:
                inverse = {value: key for key, value in aliases.items()}
                ports = [common.Port(inverse.get(p.name, p.name) if p.direction == 'output' else p.name,
                                     p.direction, p.width, p.signed) for p in ports]
            portsets.append(ports)
            side_delays = {name: max(0, lag if side == 'gold' else -lag) for name, lag in delays.items()}
            (directory / 'wrapper.v').write_text(harness(args, ports, delays=side_delays,
                                                       aliases=aliases if side == 'gate' else {},
                                                       encoding=(encoding_rows, side, bodies[-1]) if encoding_rows else None))
            snapshot.seal(directory / 'wrapper.v')
        if portsets[0] != portsets[1]:
            raise ValueError('design port interfaces differ')
        result['state_mapping'], result['unmatched'] = mapping(*bodies, args.pair)
        if encoding_rows:
            if any(pair.split('=')[index] == row[side] for pair in args.pair
                   for row in encoding_rows for index, side in enumerate(('gold','gate'))):
                raise ValueError('pair and state-encoding must not name the same register')
            state_encoding.audit(encoding_rows, bodies, result['state_mapping'], result['unmatched'])
        # Match only boundary ports in the proof. State mappings are audited coverage,
        # never assumed equal. Thus a FAIL is an output counterexample, not a cutpoint failure.
        lines = []
        for side, model in zip(('gold', 'gate'), proof_models):
            lines += [f'[{side}]', f'read_rtlil {model}',
                      f'read_verilog {"-formal " if sampled else ""}{out / side / "wrapper.v"}', 'prep -top rvw_equiv -flatten',
                      *(['clk2fflogic'] if sampled else []),
                      'setundef -undriven -anyseq']
        lines += ['[match rvw_equiv]']
        for p in portsets[0]:
            if p.name != args.reset:
                lines.append(f'gold-match {p.name}')
        if encoding_rows:
            lines += [f'gold-match {name}' for name in state_encoding.observations(encoding_rows)]
        lines += ['gold-nomatch *', '[collect rvw_equiv]', 'join *',
                  '[strategy scorr]', 'use sby', 'engine abc scorr; pdr', 'xprop off',
                  f'timeout {max(1, int(budget()))}']
        config = out / 'equiv.eqy'
        config.write_text('\n'.join(lines) + '\n')
        from .snapshot import digest
        result['config'] = {'path': 'equiv.eqy', 'sha256': digest(config)}
        snapshot.tools._pin('eqy')
        snapshot.tools._pin('make')
        if args.dsec:
            result['dsec'] = dsec(out, budget)
        rc, _ = common.run(['eqy', '-j', '1', '-d', str(out / 'eqy'), str(config)],
                           out, out / 'eqy.log', budget())
        plist = out / 'eqy/partition.list'
        if plist.exists():
            for line in plist.read_text().splitlines():
                name = line.split()[1]
                status = out / 'eqy/strategies' / name / 'scorr/status'
                metadata = json.loads((out / 'eqy/partitions' / f'{name}.json').read_text())
                cuts = metadata['partition']['crossbits']
                result['partitions'].append({'name': name, 'crossbits': cuts,
                    'status': status.read_text().strip() if status.exists() and cuts == {} else 'UNKNOWN'})
        result['traces'] = sorted(str(p.relative_to(out)) for p in (out / 'eqy').glob('strategies/**/trace*.vcd'))
        proof_complete = rc == 0 and (out / 'eqy/PASS').is_file()
        result['status'] = verdict(0 if proof_complete else (rc or 1), rc == 124, result['partitions'],
                                   result['unmatched'] if args.unmatched_state == 'refuse' else {}, result['traces'])
        if encoding_rows:
            if result['status'] == 'equivalent':
                result['encoding_verdict'] = 'proved'
            elif result['status'] == 'not_equivalent':
                result['status'] = 'inconclusive'
                result['reason'] = 'output or encoding obligation failed; rerun without the mapping to classify output differences'
        result['solver_exit'] = rc
    except SystemExit as exc:
        result['reason'] = f'input or elaboration refused (exit {exc.code}); see logs'
    except (ValueError, OSError, KeyError, TypeError, CaptureError, TimeoutError) as exc:
        result['reason'] = str(exc)
    except BaseException:
        common.release(args)
        raise
    finally:
        for snapshot in snapshots:
            record = {}
            snapshot.finish(record)
            result.setdefault('inputs', []).append(record)
            if record.get('status') == 'unknown':
                result['status'] = 'inconclusive'
        ACTIVE.reset(token)
    if ('blackbox_contract' in result or 'event_model' in result) and result['status'] in ('equivalent','not_equivalent'):
        result['contract_verdict'] = result['status']
        result['status'] = 'conditional'
    result['wall_s'] = round(time.monotonic() - started, 3)
    try:
        common.write_json(out / 'result.json', result)
    finally:
        common.release(args)
    print(json.dumps(result, indent=2) if args.json else f"equiv: {result['status']} ({out / 'result.json'})")
    return 0 if result['status'] == 'equivalent' else 1


def dsec(out, budget):
    """Advisory only: ABC dsec uses its own initialization and matching model."""
    for side in ('gold', 'gate'):
        directory = out / side
        script = (f'read_rtlil {directory / "module_ports.il"}\n'
                  f'read_verilog {directory / "wrapper.v"}\n'
                  'synth -top rvw_equiv -flatten\ndffunmap\naigmap\n'
                  f'write_aiger -zinit -symbols {directory / "design.aig"}\n')
        (directory / 'aig.ys').write_text(script)
        rc, _ = common.run(['yosys', '-Q', '-s', 'aig.ys'], directory, directory / 'aig.log', budget())
        if rc == 124:
            raise TimeoutError('dsec AIG export timed out')
        if rc:
            raise ValueError('dsec AIG export failed')
    rc, _ = common.run(['yosys-abc', '-c', f'dsec -T {max(1, int(budget()))} {out / "gold/design.aig"} {out / "gate/design.aig"}'],
                       out, out / 'dsec.log', budget())
    if rc == 124:
        raise TimeoutError('dsec timed out')
    text = (out / 'dsec.log').read_text()
    if rc or not any(marker in text for marker in ('Networks are equivalent', 'Networks are NOT EQUIVALENT')):
        raise ValueError('dsec did not complete a comparison; see dsec.log')
    return {'exit': rc, 'log': 'dsec.log', 'authoritative': False}
