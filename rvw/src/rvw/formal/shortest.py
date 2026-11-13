"""Search increasing solver depths for one captured assertion."""
from pathlib import Path
import json
import time
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from .common import write_json


def search(max_depth, check):
    attempts = []
    for depth in range(1, max_depth + 1):
        row = dict(check(depth), depth=depth)
        attempts.append(row)
        if row['status'] == 'fail':
            return {'status': 'fail', 'depth': depth,
                    'shortest': all(r['status'] == 'pass' for r in attempts[:-1]), 'attempts': attempts}
        if row['status'] not in ('pass', 'fail'):
            return {'status': 'inconclusive', 'depth': None, 'shortest': False, 'attempts': attempts}
    return {'status': 'inconclusive', 'depth': None, 'shortest': False, 'attempts': attempts}


def run(args):
    if args.max_depth < 1 or args.timeout <= 0:
        raise ValueError('max-depth and timeout must be positive')
    root = Path(args.result).resolve()
    if root.is_dir():
        root /= 'result.json'
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    original = json.loads(capture.file(root).copy.read_text())
    if original.get('schema') != 'rvw.formal/1' or original.get('assertions') != 1 or original.get('flow') != 'bmc':
        raise ValueError('shortest search needs a captured BMC model with exactly one assertion')
    model = capture.file(root.parent / 'sby/model/design.il').copy
    sby = capture.tool('sby', identity_only=True)
    yosys = capture.tool('yosys')
    metadata = out / 'model.json'
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', f'read_rtlil {json.dumps(str(model))}; write_json {json.dumps(str(metadata))}'], capture=True, timeout=args.timeout)
    if proc.returncode:
        raise ValueError('cannot read captured model')
    modules = json.loads(metadata.read_text())['modules']
    tops = [n for n, m in modules.items() if int(m.get('attributes', {}).get('top', '0'), 2)]
    if len(tops) != 1:
        raise ValueError('captured model needs one top')
    top = tops[0]
    from .common import check_ident
    check_ident('top', top)
    deadline = time.monotonic() + args.timeout
    def check(depth):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'status': 'timeout'}
        script = out / f'depth-{depth}.sby'
        script.write_text(f'[options]\nmode bmc\ndepth {depth}\n[engines]\n{args.engine.replace(":", " ")}\n'
                          f'[script]\nread_rtlil {json.dumps(str(model))}\nprep -top {top}\nchformal -remove -cover\n')
        directory = out / f'depth-{depth}'
        proc = run_group([str(sby.path), '-f', '-d', str(directory), str(script)], capture=True, timeout=remaining)
        (out / f'depth-{depth}.log').write_text((proc.stdout or '') + (proc.stderr or ''))
        path = directory / 'status'
        native = path.read_text().strip().split()[0] if path.exists() else 'ERROR'
        status = 'pass' if native == 'PASS' and proc.returncode == 0 else (
            'fail' if native == 'FAIL' and proc.returncode != 0 else 'inconclusive')
        return {'status': status, 'native_status': native, 'exit_code': proc.returncode, 'directory': directory.name}
    report = search(args.max_depth, check)
    capture.verify_tools()
    report.update(schema='rvw.shortest-cex/1', property=original.get('failures', []),
                  restrictions=original.get('restrictions', []), input_capture=capture.record(),
                  scope='Shortest solver sample depth for the sole captured assertion under the original assumptions. No unbounded proof. Trace files remain in each SBY directory.')
    write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else report['status'])
    return 1
