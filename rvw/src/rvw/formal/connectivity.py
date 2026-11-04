"""Resolve declared connectivity in a captured SpinalDB graph.

A dependency path is a structural candidate, not a value-transfer proof.
"""
from collections import deque
import json
from pathlib import Path
import tomllib

from rvw.query.db import DesignDB, QueryError, SCHEMA


def resolve(db, rule, *, max_nodes=200000):
    """Keep missing endpoints, truncated cones and opaque logic incomplete."""
    unknown = set(rule) - {'id', 'kind', 'source', 'destination', 'latency', 'mode', 'enable'}
    if unknown:
        raise ValueError(f'unknown connection fields: {sorted(unknown)}')
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError('max_nodes must be a positive integer')
    if rule.get('kind') not in ('required', 'forbidden'):
        raise ValueError('connection kind must be required or forbidden')
    if type(rule.get('latency', 0)) is not int or rule.get('latency', 0) < 0:
        raise ValueError('latency must be a nonnegative integer')
    for key in ('id', 'source', 'destination'):
        if not isinstance(rule.get(key), str) or not rule[key]:
            raise ValueError(f'connection needs {key}')
    result = {'id': rule['id'], 'declaration': dict(rule), 'status': 'incomplete',
              'semantic_status': 'not_run', 'structural_status': 'incomplete'}
    try:
        if db.schema != SCHEMA:
            raise QueryError('connectivity requires the current SpinalDB schema')
        db.require_inout_edges()
        src = db.resolve_one(rule['source'])
        dst = db.resolve_one(rule['destination'])
        result['endpoints'] = {'source': src.path, 'destination': dst.path}
        if rule['kind'] == 'required' and src.width != dst.width:
            raise QueryError('required value-transfer endpoint widths differ')
        result['conditions'] = {}
        for key in ('mode', 'enable'):
            if key in rule:
                if not isinstance(rule[key], str) or not rule[key]:
                    raise QueryError(f'{key} must name one active-high Boolean signal')
                sig = db.resolve_one(rule[key])
                if sig.width != 1:
                    raise QueryError(f'{key} must be one bit')
                result['conditions'][key] = sig.path
        # Traverse the complete destination cone. A shortest path alone can hide
        # an alternate opaque route. Retain clock, reset, init and control edges.
        queue = deque([dst.id])
        parent = {dst.id: None}
        opaque = set()
        truncated = False
        while queue:
            sid = queue.popleft()
            signal = db.signal_by_id(sid)
            if db.component(signal.component_id)['blackbox']:
                opaque.add(signal.path)
            for origin, kind in db.q('SELECT src, kind FROM edges WHERE dst=?', (sid,)):
                if kind == 'blackbox':
                    opaque.add(signal.path)
                if origin not in parent:
                    if len(parent) >= max_nodes:
                        truncated = True
                        continue
                    parent[origin] = (sid, kind)
                    queue.append(origin)
        result.update(searched_signals=len(parent), opaque=sorted(opaque), truncated=truncated)
        if opaque or truncated:
            result['reason'] = 'opaque destination cone' if opaque else 'destination cone limit reached'
            return result
        found = src.id in parent
        result['structural_status'] = 'dependency_found' if found else 'dependency_absent'
        result['path'] = []
        current = src.id
        while found:
            step = parent[current]
            result['path'].append({'signal': db.signal_by_id(current).path,
                                   'kind': step[1] if step else None})
            if step is None:
                break
            current = step[0]
        result['reason'] = ('structural graph only; mode, enable and latency obligations need a formal campaign')
        # Deliberately no pass/fail verdict. A path does not prove a transfer;
        # absence does not discharge the declared temporal environment.
        return result
    except QueryError as exc:
        result['reason'] = str(exc)
        if exc.candidates:
            result['candidates'] = exc.candidates
        return result


def run(args):
    from rvw.common.capture import Capture
    import math
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    manifest = capture.file(Path(args.manifest).absolute())
    plan = tomllib.loads(manifest.copy.read_text())
    if set(plan) != {'connection'}:
        raise ValueError('manifest supports only connection declarations')
    rows = plan.get('connection')
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError('manifest needs [[connection]] rows')
    ids = [row.get('id') for row in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('connection IDs must be nonempty and unique')
    db = DesignDB(args.db, capture=capture)
    try:
        result = {'schema': 'rvw.connectivity/1', 'status': 'incomplete',
                  'scope': 'captured SpinalDB graph with optional bounded top-port contracts; no design acceptance verdict',
                  'database_sha256': db.input.sha256, 'database_schema': db.schema,
                  'connections': [resolve(db, row, max_nodes=args.max_nodes) for row in rows],
                  'input_capture': capture.record()}
        if args.run:
            for i, (row, entry) in enumerate(zip(rows, result['connections'])):
                if entry['structural_status'] == 'incomplete':
                    continue
                directory = out / f'connection-{i}'
                directory.mkdir()
                try:
                    entry['campaign'] = campaign(db, row, directory, capture, args)
                    entry['semantic_status'] = entry['campaign']['status']
                    entry['reason'] = 'bounded campaign observation; general internal RTL binding remains incomplete'
                except (ValueError, QueryError) as exc:
                    entry['reason'] = str(exc)
        result['input_capture'] = capture.record()
    finally:
        db.close()
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2) if args.json else
          '\n'.join(f"{r['id']}: {r['structural_status']} (incomplete)" for r in result['connections']))
    return 1


def register(sub):
    parser = sub.add_parser('connectivity', help='resolve SpinalDB connections and run bounded top-port contracts')
    parser.add_argument('manifest', help='TOML with [[connection]] declarations')
    parser.add_argument('--db', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--max-nodes', type=int, default=200000)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--run', action='store_true', help='also run bounded top-port contracts')
    parser.add_argument('--clock', default='clk')
    parser.add_argument('--reset', default='reset')
    parser.add_argument('--depth', type=int, default=10)
    parser.add_argument('--engine', default='smtbmc:yices')
    parser.add_argument('--timeout', type=float, default=60)
    parser.set_defaults(func=cli_run)


def cli_run(args):
    from rvw.common.capture import CaptureError
    from .common import die
    try:
        return run(args)
    except (ValueError, OSError, QueryError, CaptureError) as exc:
        die(str(exc))


def harness(db, declaration, *, clock='clk', reset='reset', activation=False):
    """Bind top ports only. Internal signals need a future RTL binding backend.

    Forbidden connections use two copies with common inputs except source.
    Their initial state is independent. A pass is stronger than equal-state
    noninterference; a failure can need initial-state triage.
    """
    from .common import check_ident
    top = check_ident('database top', db.top)
    if top == 'rvw_connection_top':
        raise ValueError('reserved connectivity wrapper name')
    signals = db.signals_where("s.direction IS NOT NULL AND s.pruned=0")
    ports = {s.name: s for s in signals if db.component(s.component_id)['parent_id'] is None}
    for name in ports:
        check_ident('port', name)
    for name in (clock, reset):
        if name not in ports or ports[name].direction != 'in' or ports[name].width != 1:
            raise ValueError('campaign needs declared one-bit top clock and reset inputs')
    bound = {k: db.resolve_one(declaration[k]) for k in ('source', 'destination', 'mode', 'enable') if k in declaration}
    for key, signal in bound.items():
        if signal.id not in {p.id for p in ports.values()}:
            raise ValueError(f'{key}: internal RTL binding is not supported')
    source, destination = bound['source'], bound['destination']
    if source.direction != 'in' or destination.direction != 'out':
        raise ValueError('campaign needs input source and output destination')
    for key in ('mode', 'enable'):
        if key in bound and (bound[key].direction != 'in' or bound[key].name == source.name):
            raise ValueError('mode and enable must be common inputs distinct from source')
    if source.name in (clock, reset):
        raise ValueError('clock and reset cannot be data sources')
    if any(p.direction not in ('in', 'out') for p in ports.values()):
        raise ValueError('inout ports need a connectivity backend')
    aliases = {name: f'p{i}' for i, name in enumerate(ports)}
    aliases[clock], aliases[reset] = 'clk', 'reset'
    inputs = [f'input [{p.width-1}:0] {aliases[n]}' for n, p in ports.items() if p.direction == 'in']
    forbidden = declaration['kind'] == 'forbidden'
    if forbidden:
        inputs.append(f'input [{source.width-1}:0] alternate_source')
    lines = ['module rvw_connection_top(' + ', '.join(inputs) + ');']
    for side in ('a', 'b') if forbidden else ('a',):
        conns = []
        for name, port in ports.items():
            wire = aliases[name]
            if port.direction == 'out':
                wire += '_' + side
                lines.append(f'wire [{port.width-1}:0] {wire};')
            elif side == 'b' and name == source.name:
                wire = 'alternate_source'
            conns.append(f'.{name}({wire})')
        lines.append(f'{top} dut_{side}(' + ', '.join(conns) + ');')
    guard = ' && '.join(aliases[bound[k].name] for k in ('mode', 'enable') if k in bound) or "1'b1"
    expected, valid = aliases[source.name], f'({guard})'
    for i in range(declaration.get('latency', 0)):
        lines += [f'reg [{source.width-1}:0] expected_{i};', f'reg valid_{i};',
                  f'always @(posedge clk) begin expected_{i} <= {expected}; '
                  f'if (reset) valid_{i} <= 0; else valid_{i} <= {valid}; end']
        expected, valid = f'expected_{i}', f'valid_{i}'
    lhs = aliases[destination.name] + '_a'
    rhs = aliases[destination.name] + '_b' if forbidden else expected
    expression = f'!({valid})' if activation else f'{lhs} == {rhs}'
    condition = '!reset' if activation else f'!reset && {valid}'
    lines += [f'always @(posedge clk) if ({condition}) assert({expression});', 'endmodule']
    return '\n'.join(lines) + '\n'


def campaign(db, declaration, out, capture, args):
    """Reuse the captured native BMC flow and independently witness activation."""
    import sys
    from rvw.common.proc import run_group
    if args.depth < declaration.get('latency', 0) + 4:
        raise ValueError('depth must be at least latency + 4')
    files = []
    for path, in db.q('SELECT path FROM rtl_files'):
        item = capture.file(Path(path))
        expected = db.q('SELECT sha256 FROM input_files WHERE path=?', (path,))
        if expected != [(item.sha256,)]:
            raise ValueError('RTL does not match the database content binding')
        files.append(str(item.copy))
    if not files:
        raise ValueError('database has no RTL files')
    observations = {}
    for name in ('transfer', 'activation'):
        directory = out / name
        directory.mkdir()
        source = directory / 'connection.sv'
        source.write_text(harness(db, declaration, clock=args.clock, reset=args.reset,
                                  activation=name == 'activation'))
        command = [sys.executable, '-m', 'rvw', 'formal', 'bmc', '--verilog', *files, str(source),
                   '--top', 'rvw_connection_top', '--clock', 'clk', '--reset', 'reset',
                   '--depth', str(args.depth), '--engine', args.engine, '--timeout', str(args.timeout),
                   '--reset-cycles', '1', '--first-failure', '--out', str(directory/'bmc')]
        with (directory/'command.log').open('w') as log:
            process = run_group(command, cwd=out, stdout=log, stderr=log, timeout=args.timeout + 30)
        result_path = directory/'bmc/result.json'
        result = json.loads(result_path.read_text()) if result_path.is_file() else {}
        status = result.get('status', 'error')
        expected_rc = {'pass': 0, 'fail': 1}.get(status)
        if (process.timed_out or result.get('assertions') != 1
                or expected_rc is not None and process.returncode != expected_rc):
            status = 'incomplete'
        observations[name] = {'status': status, 'result': str(result_path),
                              'returncode': process.returncode}
    transfer, activation = (observations[k]['status'] for k in ('transfer', 'activation'))
    return {'status': 'bounded_pass' if transfer == 'pass' and activation == 'fail' else 'incomplete',
            'depth': args.depth, 'observations': observations,
            'semantics': 'mode and enable sampled with source; fixed cycle latency; synchronous active-high reset',
            'initial_state': 'independent DUT copies for forbidden influence; counterexamples need state triage',
            'scope': 'two-state bounded top-port contract under captured DUT assumptions; no design acceptance verdict'}
