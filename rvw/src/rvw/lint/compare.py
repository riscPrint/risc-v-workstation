"""Same-input CDC qualification. Expected results come from the suite author."""
from argparse import Namespace
import contextlib
import hashlib
import io
import json
from pathlib import Path

from rvw.common.proc import run_group
from rvw.formal import apps, common
from . import protocol


def adapter(command, request, directory, timeout):
    """A trusted adapter observation is not an independently replayed proof."""
    directory.mkdir()
    request_file, response_file = directory / 'request.json', directory / 'response.json'
    common.write_json(request_file, request)
    digest = hashlib.sha256(request_file.read_bytes()).hexdigest()
    run = run_group([command, str(request_file), str(response_file)], timeout=timeout, capture=True)
    (directory / 'adapter.log').write_text((run.stdout or '') + (run.stderr or ''))
    if run.timed_out or run.returncode != 0 or not response_file.exists():
        return dict(status='inconclusive', reason='adapter did not complete')
    try:
        result = json.loads(response_file.read_text())
        if (result.get('schema') != 'rvw.cdc-adapter-response/1' or result.get('request_sha256') != digest
                or result.get('mode') != request.get('mode')
                or result.get('status') not in ('pass','fail','inconclusive')
                or not isinstance(result.get('tool_version'), str) or not result['tool_version'].strip()):
            raise ValueError('invalid adapter response identity or fields')
        if (result['status'] == 'pass' and request.get('mode') == 'bmc'
                and (type(result.get('reached_depth')) is not int or result['reached_depth'] < request['depth'] - 1)):
            raise ValueError('adapter BMC prefix is shorter than requested depth')
        return dict(status=result['status'], tool_version=result['tool_version'], evidence='trusted adapter observation')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return dict(status='inconclusive', reason=str(exc))


def run(args):
    path = Path(args.benchmark).resolve()
    plan = json.loads(path.read_text())
    if plan.get('schema') != 'rvw.cdc-bench/1' or set(plan) - {'schema','cases','adapters'}:
        raise ValueError('expected rvw.cdc-bench/1')
    cases = plan.get('cases')
    if not isinstance(cases,list) or not cases:
        raise ValueError('cases must be nonempty')
    adapters = plan.get('adapters', [])
    if not isinstance(adapters, list):
        raise ValueError('adapters must be a list')
    ids = []
    for a in adapters:
        ids.append(apps.ident(a['id']))
        if not isinstance(a['command'],str) or not Path(a['command']).is_absolute() or not Path(a['command']).is_file():
            raise ValueError('adapter command must be an absolute executable file')
    if len(ids) != len(set(ids)) or 'native' in ids:
        raise ValueError('duplicate adapter IDs')
    # Validate and read all sources before starting any tool.
    frozen, names = [], []
    for case in cases:
        name = apps.ident(case['id']); names.append(name)
        if case['expected'] not in ('pass','fail'):
            raise ValueError('expected must be pass or fail')
        spec_path = (path.parent / case['manifest']).resolve()
        spec = json.loads(spec_path.read_text()); protocol.generate(spec)
        source_paths = [(spec_path.parent / p).resolve() for p in spec['verilog']]
        contents = [p.read_bytes() for p in source_paths]
        hashes = [hashlib.sha256(d).hexdigest() for d in contents]
        if hashes != case['source_sha256']:
            raise ValueError('source hash mismatch: ' + name)
        frozen.append((case,spec,contents,hashes))
    if len(names) != len(set(names)):
        raise ValueError('duplicate case IDs')
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    rows = []
    for case,spec,contents,hashes in frozen:
        root = out / case['id']; root.mkdir()
        files = []
        for i,data in enumerate(contents):
            p = root / f'source{i}.sv'; p.write_bytes(data); files.append(str(p))
        spec = {**spec, 'verilog':files}
        manifest = root / 'spec.json'; common.write_json(manifest,spec)
        child = Namespace(protocol=str(manifest), out=str(root / 'native'), depth=args.depth,
                          mode=args.mode, engine=args.engine, timeout=args.timeout,
                          simulate=0, seed=1, json=False)
        with contextlib.redirect_stdout(io.StringIO()):
            protocol.run(child)
        native = json.loads((root / 'native' / 'result.json').read_text())
        observations = {'native':dict(status=native['status'], proof_kind=native['proof_kind'])}
        # Do not send the expected verdict. It remains the independent suite oracle.
        request = dict(schema='rvw.cdc-adapter-request/1', case_id=case['id'], spec=spec,
                       source_sha256=hashes, monitor=str(root / 'native' / 'monitor.sv'),
                       mode=args.mode, depth=args.depth)
        for a in adapters:
            observations[a['id']] = adapter(a['command'],request,root / a['id'],args.timeout)
        rows.append(dict(id=case['id'],expected=case['expected'],observations=observations))
    qualification = {}
    for tool in ['native', *ids]:
        statuses = [r['observations'][tool]['status'] for r in rows]
        qualification[tool] = ('mismatch' if any(s in ('pass','fail') and s != r['expected'] for s,r in zip(statuses,rows)) else
                               'matches_on_suite' if all(s == r['expected'] for s,r in zip(statuses,rows)) else 'inconclusive')
    report = dict(schema='rvw.cdc-bench-result/1', cases=rows, qualification=qualification,
                  commercial_comparison='not_run' if not adapters else 'trusted adapter observations only',
                  limits='Selected cases only. No commercial parity or signoff. Suite expectations are reviewed input. Native and commercial observations are not the oracle.')
    common.write_json(out / 'result.json',report)
    print(json.dumps(report,indent=2) if args.json else json.dumps(qualification))
    return 0 if all(v == 'matches_on_suite' for v in qualification.values()) else 1
