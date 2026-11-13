"""Search increasing solver depths for one captured assertion."""
from pathlib import Path
import json
import time
import re
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
    if original.get('schema') != 'rvw.formal/1' or not original.get('assertions') or original.get('flow') != 'bmc':
        raise ValueError('shortest search needs a captured BMC model with assertions')
    model = capture.file(root.parent / 'sby/model/design.il').copy
    sby = capture.tool('sby', identity_only=True)
    yosys = capture.tool('yosys')
    metadata = out / 'model.json'
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', f'read_rtlil {json.dumps(str(model))}; flatten; async2sync; chformal -lower; write_json {json.dumps(str(metadata))}'], capture=True, timeout=args.timeout)
    if proc.returncode:
        raise ValueError('cannot read captured model')
    modules = json.loads(metadata.read_text())['modules']
    tops = [n for n, m in modules.items() if int(m.get('attributes', {}).get('top', '0'), 2)]
    if len(tops) != 1:
        raise ValueError('captured model needs one top')
    top = tops[0]
    from .common import check_ident
    check_ident('top', top)
    assertions = sorted(n for n,c in modules[top]['cells'].items() if c['type'] == '$assert')
    selected = getattr(args, 'property', None) or assertions
    if not selected or set(selected) - set(assertions) or len(selected) != len(set(selected)):
        raise ValueError('select unique assertion cell names from the captured model')
    if any(not re.fullmatch(r'[A-Za-z0-9_.$/:=+-]+', n) for n in assertions):
        raise ValueError('unsupported assertion selection name')
    hgldd = capture.tree(Path(args.hgldd), git=False).copy if getattr(args, 'hgldd', None) else None
    deadline = time.monotonic() + args.timeout
    reports = []
    for index, prop in enumerate(selected):
        directory = out / f'property-{index}'
        directory.mkdir()
        isolated = directory / 'model.il'
        remove = '; '.join('chformal -remove -assert ' + top+'/c:'+n for n in assertions if n != prop)
        script = f'read_rtlil {json.dumps(str(model))}; flatten; async2sync; chformal -lower; ' + remove + f'; select -assert-count 1 {top}/t:$assert; select *; write_rtlil {json.dumps(str(isolated))}'
        proc = run_group([str(yosys.path), '-Q', '-T', '-p', script], capture=True, timeout=max(.001, deadline-time.monotonic()))
        (directory/'isolate.log').write_text((proc.stdout or '')+(proc.stderr or ''))
        if proc.returncode:
            reports.append(dict(property_id=prop,status='inconclusive',shortest=False,depth=None,attempts=[],reason='isolation failed'))
            continue
        def check(depth):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {'status': 'timeout'}
            job = directory / f'depth-{depth}.sby'
            job.write_text(f'[options]\nmode bmc\ndepth {depth}\n[engines]\n{args.engine.replace(":", " ")}\n'
                          f'[script]\nread_rtlil {json.dumps(str(isolated))}\nprep -top {top}\nchformal -remove -cover\n')
            target = directory / f'depth-{depth}'
            proc = run_group([str(sby.path), '-f', '-d', str(target), str(job)], capture=True, timeout=remaining)
            (directory / f'depth-{depth}.log').write_text((proc.stdout or '') + (proc.stderr or ''))
            path = target / 'status'
            native = path.read_text().strip().split()[0] if path.exists() else 'ERROR'
            status = 'pass' if native == 'PASS' and proc.returncode == 0 else (
                'fail' if native == 'FAIL' and proc.returncode != 0 else 'inconclusive')
            return {'status': status, 'native_status': native, 'exit_code': proc.returncode, 'directory': str(target.relative_to(out))}
        row = dict(search(args.max_depth, check), property_id=prop)
        if hgldd and row['status'] == 'fail':
            row['typed_output'] = typed_output(directory/f'depth-{row["depth"]}', hgldd, original.get('top', top), directory, capture, max(.001, deadline-time.monotonic()))
        reports.append(row)
    if len(reports) == 1:
        report = dict(reports[0])
    else:
        report = dict(status='fail' if any(r['status']=='fail' for r in reports) else 'inconclusive')
    report['properties'] = reports
    capture.verify_tools()
    report.update(schema='rvw.shortest-cex/1', property=original.get('failures', []),
                  restrictions=original.get('restrictions', []), input_capture=capture.record(),
                  scope='Independent shortest solver sample depths for selected captured assertions under the original assumptions. No unbounded proof. Trace files remain in each SBY directory.')
    write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else report['status'])
    return 1


def typed_output(run, hgldd, top, out, capture, timeout):
    import shutil
    waves = sorted(run.glob('engine_*/trace*.vcd'))
    exe = shutil.which('spinalwaves-check')
    if not waves or not exe:
        return dict(status='inconclusive', reason='witness VCD or spinalwaves-check missing')
    tool = capture.tool(exe, identity_only=True)
    target = out/'typed.vcd'
    stack, paths = [], []
    header = waves[0].read_text().split('$enddefinitions', 1)[0]
    for match in re.finditer(r'\$scope\s+\w+\s+(\S+)\s+\$end|\$upscope\s+\$end', header):
        if match[1]:
            stack.append(match[1]); paths.append(list(stack))
        elif stack: stack.pop()
    scopes = next((p for p in paths if p[-1] == 'dut'), next((p for p in paths if p[-1] == top), []))
    command = [str(tool.path),'--vcd',str(waves[0]),'--hgldd',str(hgldd),'--top-module',top,'--extra-scopes',*scopes,'--out',str(target)]
    proc = run_group(command,capture=True,timeout=timeout)
    (out/'spinalwaves-check.log').write_text((proc.stdout or '')+(proc.stderr or ''))
    return dict(status='completed' if proc.returncode==0 and target.exists() else 'inconclusive',
                output=str(target), exit_code=proc.returncode, command=command)
