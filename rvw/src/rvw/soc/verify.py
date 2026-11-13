"""Generate SoC verification inputs and execute project-owned consumers.

A process exit code alone is not verification evidence. Each run must publish a
fresh result with the declared kind, positive check count and explicit verdict.
"""
import hashlib
import json
from pathlib import Path

from rvw.common.proc import run_group
from rvw.query.db import QueryError
from .model import load, dumps

KINDS = ('protocol', 'registers', 'vip', 'uvm', 'connectivity', 'decode', 'cdc_rdc')


def generate(source, out, settings):
    """Reuse the consumers. Keep unsupported bindings in each generated report."""
    source, out = Path(source).resolve(), Path(out).resolve()
    model = load(source)
    out.mkdir(parents=True, exist_ok=False)
    (out/'map.json').write_text(dumps(model))
    rows = []
    for kind in KINDS:
        row = dict(kind=kind, generated=False, ran=False, result='inconclusive')
        rows.append(row)
        entry = settings.get(kind, {})
        try:
            if kind == 'protocol' and entry.get('database'):
                from rvw.formal.bus_bindings import generate as buses
                report = buses(entry['database'], out/kind, clocks=entry.get('clocks'))
                row['generated'] = report['status'] == 'generated'
                row['complete'] = report['complete']
                row['details'] = report
            elif kind == 'vip' and entry.get('database'):
                from rvw.vip.catalog import buses, skeleton
                report = []
                for index, bus in enumerate(buses(entry['database'])['buses']):
                    report.append(skeleton(entry['database'], out/kind/f'bus_{index}.py', bus['path'],
                                           entry.get('clock', 'clk'), entry.get('reset', 'reset_n')))
                row['generated'] = bool(report)
                row['details'] = report
                row['reason'] = 'Bench skeletons need project stimulus and expectations.'
            elif kind == 'uvm' and entry.get('database'):
                from rvw.uvm.scaffold import generate as uvm
                report = uvm(entry['database'], source, out/kind, language='pyuvm')
                row['generated'] = True
                row['details'] = report
            elif kind == 'cdc_rdc' and entry.get('database'):
                from rvw.query.db import DesignDB
                from rvw.lint.structural import analyze
                db = DesignDB(entry['database'])
                try:
                    report = analyze(db, entry.get('intent'))
                finally:
                    db.close()
                (out/'cdc_rdc.json').write_text(dumps(report))
                row.update(generated=True, ran=True, result='inconclusive', details=report)
            elif kind in ('protocol', 'vip'):
                from rvw.formal.simple_bus_checks import render
                directory = out/kind
                directory.mkdir()
                if kind == 'protocol':
                    (directory/'monitors.sv').write_text(render('apb', 65, 1))
                    bindings = []
                    for region in model['regions']:
                        name = region['name']
                        pin = lambda field: name+'.io_bus_'+field
                        bindings.append('bind ComposedSoc rvw_apb '+name+'_check ('+
                            '.clk(clk), .reset(reset), .select('+pin('PSEL')+'), '+
                            '.enable('+pin('PENABLE')+'), .ready('+pin('PREADY')+'), '+
                            ".error("+pin('PSLVERROR')+"), .request({32'("+pin('PADDR')+"), "+
                            pin('PWRITE')+', ('+pin('PWRITE')+' ? '+pin('PWDATA')+" : 32'b0)}));")
                    (directory/'binds.sv').write_text('\n'.join(bindings)+'\n')
                    row.update(generated=True, complete=False,
                               reason='Peripheral binds emitted; core ingress needs its typed database binding.')
                else:
                    (directory/'agents.json').write_text(dumps(dict(
                        agents=[dict(region=r['name'], protocol='apb', prefix=r['name']+'.io_bus_') for r in model['regions']],
                        status='bindings_only', stimulus='project_owned')))
                    row.update(generated=True, complete=False, reason='Agent bindings emitted; project bench stimulus is required.')
            elif kind == 'registers':
                # Use the map's real side-effect semantics, not the architectural CSR interface.
                registers = [dict(region=r['name'], address=r['base']+reg['offset'], **reg)
                             for r in model['regions'] for reg in r['registers']]
                (out/'registers.json').write_text(dumps(dict(schema='rvw.soc-register-checks/1',
                    registers=registers, observation='accepted APB request and response',
                    unknown_reset=[r['region']+'.'+r['name'] for r in registers if r['reset'] is None])))
                row.update(generated=bool(registers), complete=all(r['reset'] is not None for r in registers))
            elif kind == 'decode':
                ordered = sorted(model['regions'], key=lambda r:r['base'])
                holes, end = [], 0
                for region in ordered:
                    if end < region['base']:
                        holes.append(dict(base=end, size=region['base']-end))
                    end = region['base']+region['size']
                if end < 1 << model['address_bits']:
                    holes.append(dict(base=end, size=(1 << model['address_bits'])-end))
                (out/'decode.json').write_text(dumps(dict(windows=ordered, unmapped=holes,
                    obligations=['one-hot selection', 'map-equivalent selection', 'unmapped error completion'],
                    status='not_run', note='Map arithmetic is not an RTL proof.')))
                row['generated'] = True
            elif kind == 'connectivity' and entry.get('manifest'):
                from rvw.soc.connectivity import load as connections
                report = connections(entry['manifest'])
                (out/'connections.json').write_text(dumps(dict(connection=report)))
                row.update(generated=True, details=report)
            else:
                row['reason'] = 'No consumer binding supplied.'
        except (ValueError, KeyError, TypeError, OSError, QueryError) as exc:
            row['reason'] = str(exc)
        if not row['ran']:
            row.setdefault('reason', 'Generated inputs require a bound RTL consumer run.')
    return rows


def execute(row, entry, root, out, timeout):
    """Run a bounded consumer, then validate fresh, nonempty evidence."""
    command = entry.get('command')
    if command is None:
        return
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        raise ValueError('consumer command must be a nonempty argument list')
    result_path = out/(row['kind']+'-run.json')
    # The per-kind path is in a fresh directory. A prior result cannot count.
    substitutions = {'{out}': str(out), '{result}': str(result_path), '{map}': str(out/'map.json')}
    argv = []
    for arg in command:
        for key, value in substitutions.items():
            arg = arg.replace(key, value)
        argv.append(arg)
    row['command'] = argv
    with (out/(row['kind']+'.log')).open('w') as log:
        process = run_group(argv, cwd=root, stdout=log, stderr=log, timeout=timeout)
    row.update(ran=True, returncode=process.returncode, timed_out=process.timed_out)
    if process.timed_out:
        row['reason'] = 'Consumer timed out.'
        return
    try:
        evidence = json.loads(result_path.read_text())
        if (evidence.get('schema') != 'rvw.soc-verify-evidence/1' or evidence.get('kind') != row['kind']
                or evidence.get('map_sha256') != hashlib.sha256((out/'map.json').read_bytes()).hexdigest()
                or type(evidence.get('checks')) is not int or evidence['checks'] <= 0):
            raise ValueError('Consumer evidence needs matching map hash, kind and positive checks.')
        verdict = evidence.get('status')
        allowed = ('proven', 'fail', 'inconclusive') if row['kind'] in ('decode','connectivity') else ('pass','fail','inconclusive')
        if verdict not in allowed:
            raise ValueError('Consumer verdict does not match the check kind.')
        if verdict in ('pass', 'proven') and process.returncode != 0:
            raise ValueError('Successful evidence conflicts with consumer exit code.')
        row.update(result=verdict, evidence=evidence)
        row.pop('reason', None)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        row['reason'] = str(exc)


def verify(source, out, manifest=None, timeout=120):
    if not 0 < timeout <= 120:
        raise ValueError('timeout must be greater than zero and at most 120 seconds per consumer')
    source, out = Path(source).resolve(), Path(out).resolve()
    settings, root = {}, source.parent
    if manifest:
        path = Path(manifest).resolve()
        spec = json.loads(path.read_text())
        if set(spec)-{'schema','checks','prepare'} or not {'schema','checks'} <= set(spec) or spec['schema'] != 'rvw.soc-verify/1':
            raise ValueError('expected rvw.soc-verify/1 with checks')
        settings, root = spec['checks'], path.parent
        if not isinstance(settings, dict) or set(settings)-set(KINDS):
            raise ValueError('unknown SoC verification kind')
        for entry in settings.values():
            if not isinstance(entry, dict):
                raise ValueError('check settings must be dictionaries')
            for key in ('database', 'clocks', 'manifest', 'classpath_file', 'composition'):
                if key in entry:
                    entry[key] = str((root/entry[key]).resolve())
    rows = generate(source, out, settings)
    if manifest and spec.get('prepare'):
        command = spec['prepare']
        if not isinstance(command, list) or not command or not all(isinstance(a,str) for a in command):
            raise ValueError('prepare must be a nonempty argument list')
        argv = [a.replace('{out}', str(out)).replace('{map}', str(source)) for a in command]
        with (out/'prepare.log').open('w') as log:
            prepared = run_group(argv, cwd=root, stdout=log, stderr=log, timeout=timeout)
        if prepared.returncode or prepared.timed_out:
            for row in rows:
                row['reason'] = 'Preparation failed; see prepare.log.'
            result = dict(schema='rvw.soc-verify-result/1',status='inconclusive',checks=rows)
            (out/'result.json').write_text(dumps(result))
            return result
    for row in rows:
        try:
            entry = settings.get(row['kind'], {})
            if row['kind'] == 'uvm' and entry.get('composition') and entry.get('classpath_file'):
                from .uvm_run import run as run_uvm
                report = run_uvm(entry['composition'],out/'uvm-run',Path(entry['classpath_file']).read_text().strip(),
                                 build_args=entry.get('build_args',[]),idle_inputs=entry.get('idle_inputs'),timeout=timeout,expected_map=source)
                row.update(generated=report['generated'],ran=report['ran'],result=report['status'],details=report)
                row.pop('reason',None)
            if row['kind'] == 'decode' and entry.get('classpath_file'):
                from .decode_proof import prove
                report = prove(source, out/'decode-proof', Path(entry['classpath_file']).read_text().strip(), min(timeout,60))
                row.update(generated=report['generated'], ran=report.get('ran',False), result=report['status'], details=report)
                row.pop('reason',None)
            if entry.get('capture') and row['kind'] in ('protocol', 'registers', 'vip'):
                from .apb_capture import check
                try:
                    capture = entry['capture'].replace('{out}', str(out))
                    report = check(source, root/capture)
                    row.update(ran=True, details=report)
                    # Finite sampled matches are not a whole-SoC verification pass.
                    row['result'] = 'inconclusive'
                    row['reason'] = report['scope']
                except AssertionError as exc:
                    row.update(ran=True, result='fail', reason=str(exc))
            if row['result'] != 'fail':
                execute(row, settings.get(row['kind'], {}), root, out, timeout)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row['reason'] = str(exc)
    status = 'fail' if any(r['result']=='fail' for r in rows) else (
        'pass' if all(r['generated'] and r.get('complete', True) and r['ran'] and r['result'] in ('pass','proven') for r in rows) else 'inconclusive')
    result = dict(schema='rvw.soc-verify-result/1', status=status, checks=rows,
                  source=str(source), map_sha256=hashlib.sha256((out/'map.json').read_bytes()).hexdigest())
    (out/'result.json').write_text(dumps(result))
    return result


def table(result):
    return '\n'.join(['kind | generated | ran | result', '--- | --- | --- | ---'] + [
        f"{r['kind']} | {'yes' if r['generated'] else 'no'} | {'yes' if r['ran'] else 'no'} | {r['result']}"
        for r in result['checks']])
