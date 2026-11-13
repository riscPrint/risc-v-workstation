"""Generate explicit constant, dead-code and FSM obligations from a port manifest."""
from argparse import Namespace
from pathlib import Path
import json
from . import apps


def expand(plan, max_properties=256, kinds=None):
    if plan.get('schema') != 'rvw.autocheck/1':
        raise ValueError('expected rvw.autocheck/1')
    properties = []
    for name, port in plan['ports'].items():
        if port['direction'] == 'output':
            for bit in range(port['width']):
                for value in (0, 1):
                    properties.append(dict(id=f'constant_{name}_{bit}_{value}', kind='stuck_at',
                                           signal=name, bit=bit, value=value))
    if plan.get('toggle', False):
        for name, port in plan['ports'].items():
            if port['direction'] == 'output':
                for bit in range(port['width']):
                    properties.append(dict(id=f'toggle_{name}_{bit}', kind='toggle', signal=name, bit=bit))
    properties.extend(plan.get('contracts', []))
    for row in plan.get('dead_code', []):
        properties.append(dict(id=row['id'], kind='dead_code', target=row['expression']))
    for fsm in plan.get('fsms', []):
        states = fsm['states']
        if len(states) != len(set(states)):
            raise ValueError('duplicate FSM state values')
        for value in states:
            properties.append(dict(id=f"fsm_{fsm['signal']}_state_{value}", kind='fsm_state',
                                   signal=fsm['signal'], value=value))
        for source, target in fsm.get('transitions', []):
            if source not in states or target not in states:
                raise ValueError('transition endpoint missing from FSM states')
            properties.append(dict(id=f"fsm_{fsm['signal']}_edge_{source}_{target}", kind='fsm_transition',
                                   signal=fsm['signal'], source_value=source, value=target))
    for prop in properties:
        prop.setdefault('module', plan['top'])
        prop.setdefault('origin', 'generated')
        location = plan.get('source_locations', {}).get(prop.get('signal'))
        if location:
            prop.setdefault('source', location)
    if kinds:
        properties = [p for p in properties if p['kind'] in kinds]
    if not properties or len(properties) > max_properties:
        raise ValueError('no properties or property count exceeds --max-properties')
    return dict(plan, schema='rvw.formal-apps/1', properties=properties)


def run(args):
    try:
        return _run(args)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'schema': 'rvw.autocheck-error/1', 'status': 'error', 'error': str(exc)}))
        return 2


def _run(args):
    path = Path(args.manifest).resolve()
    from rvw.common.capture import Capture
    capture_root = Path(args.out).resolve().with_name(Path(args.out).name + '-database-inputs')
    capture = Capture(capture_root)
    source = json.loads(capture.file(path).copy.read_text())
    missing = sorted({'top', 'verilog'} - source.keys())
    if missing:
        raise ValueError('Autocheck manifest requires ' + ', '.join(missing) +
                         '. Declare the RTL top and source files; see '
                         'docs/INTEGRATION_GUIDE.md#project-input-recipes.')
    database = None
    if getattr(args, 'db', None):
        from .database_autocheck import populate
        source, database = populate(source, args.db, capture)
    plan = expand(source, args.max_properties, getattr(args, 'kind', None))
    database_capture = capture.record()
    plan['verilog'] = [str((path.parent / p).resolve()) for p in plan['verilog']]
    if plan.get('internal_ports'):
        from .internal_exposure import expose
        files = [capture.file(Path(p)).copy for p in plan['verilog']]
        plan['verilog'] = [str(p) for p in expose(plan, files, capture_root / 'exposure', capture, args.timeout)]
        database_capture = capture.record()
    # Keep the generated plan beside the report, outside the source tree.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='rvw-autocheck-') as temporary:
        manifest = Path(temporary) / 'apps.json'
        manifest.write_text(json.dumps(plan))
        options = Namespace(**vars(args))
        options.manifest = str(manifest)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            code = apps.run(options)
        out = Path(args.out).resolve()
        report = json.loads((out / 'result.json').read_text())
        if database is not None:
            report['database'] = database
            report['database_capture'] = database_capture
        if getattr(args, 'xprop', False):
            from rvw.cli import main
            argv = ['formal', 'xprop', '--verilog', *plan['verilog'], '--top', plan['top'],
                    '--clock', plan['clock'], '--reset', plan['reset'], '--outputs',
                    '--depth', str(args.depth), '--engine', args.engine,
                    '--timeout', str(args.timeout), '--out', str(out / 'xprop')]
            with contextlib.redirect_stdout(io.StringIO()):
                main(argv)
            xresult = json.loads((out / 'xprop/result.json').read_text())
            report['xprop'] = {'status': xresult['status'], 'result': 'xprop/result.json',
                               'scope': 'Bounded X-propagation output check; native replay not requested.'}
            if xresult['status'] != 'pass' and report['status'] == 'pass':
                report['status'], code = 'inconclusive', 1
        report['counts'] = {'generated': len(plan['properties']),
            'proven': sum(p['status'] == 'pass' and p.get('proof_kind') == 'unbounded' for p in report['properties']),
            'bounded': sum(p['status'] == 'pass' and p.get('proof_kind') == 'bounded' for p in report['properties']),
            'failed': sum(p['status'] == 'fail' for p in report['properties']),
            'unsupported': len(database.get('skipped', [])) + sum('unsupported' in r for r in database.get('roles', [])) if database else 0}
        from .common import write_json
        write_json(out / 'result.json', report)
        print(json.dumps(report, indent=2) if args.json else report['status'])
        return code
