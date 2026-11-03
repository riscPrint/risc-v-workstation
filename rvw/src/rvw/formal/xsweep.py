"""Bounded module campaigns. Each module is an independent unconstrained boundary."""
import json
import os
import re
import sys
import time

from rvw.common.proc import run_group
from . import common


def sweep(args):
    from .flows import _inputs
    out = common.begin(args)
    for name in ('module_timeout', 'campaign_timeout'):
        if not getattr(args, name) > 0:
            common.die('--' + name.replace('_', '-') + ' must be positive')
    if args.checks:
        common.die('x-sweep checks module outputs; use xprop --checks for report targets')
    started = time.monotonic()
    args.timeout = min(args.timeout or args.campaign_timeout, args.campaign_timeout)
    snapshot, _, _ = _inputs(args, out, ['SYNTHESIS'])
    modules = json.loads((out / 'module_ports.json').read_text())['modules']
    selected = args.module or sorted(modules)
    absent = set(selected) - set(modules)
    if absent:
        common.die('modules not found: ' + ', '.join(sorted(absent)))
    result = {'schema': 'rvw.formal.x-sweep/1', 'top': args.top,
              'status': 'inconclusive', 'modules': []}
    for index, name in enumerate(selected):
        entry = {'module': name, 'disposition': 'inconclusive', 'inventory': []}
        result['modules'].append(entry)
        remaining = args.campaign_timeout - (time.monotonic() - started)
        if remaining <= 0:
            entry['reason'] = 'campaign time limit'
            continue
        if not re.fullmatch(common.IDENT, name):
            entry['reason'] = 'specialized module name cannot be selected as a standalone top'
            continue
        directory = out / f'module-{index}'
        common.clear_outputs(directory, 'result.json')
        cmd = [sys.executable, '-m', 'rvw', 'formal', 'xprop', '--verilog',
               *map(str, snapshot.sources), '--top', name, '--outputs', '--depth', str(args.depth),
               '--engine', args.engine, '--clock', args.clock, '--replay', args.replay,
               '--timeout', str(min(remaining, args.module_timeout)), '--out', str(directory)]
        cmd += ['--reset-active', args.reset_active]
        if args.reset:
            cmd += ['--reset', args.reset]
        for tie in args.tie or []:
            cmd += ['--tie', tie]
        if args.clock not in modules[name].get('ports', {}):
            cmd.append('--combinational')
        env = dict(os.environ)
        env.pop('RVW_PROJECT', None)
        with (out / f'module-{index}.log').open('w') as log:
            run = run_group(cmd, cwd=out, env=env, stdout=log, stderr=log,
                            timeout=min(remaining, args.module_timeout))
        entry['result'] = str(directory.relative_to(out) / 'result.json')
        if run.timed_out:
            entry['reason'] = 'module time limit'
        elif run.returncode in (0, 1) and (directory / 'result.json').exists():
            child = json.loads((directory / 'result.json').read_text())
            if (run.returncode == 0) != (child.get('status') == 'pass'):
                entry['reason'] = 'child exit code and result status disagree'
                continue
            entry.update(status=child['status'], restrictions=child.get('restrictions', []),
                         inventory=child.get('inventory', []),
                         disposition='bounded_clean' if child['status'] == 'pass' else 'inconclusive')
            if any(t['disposition'] == 'confirmed' for t in entry['inventory']):
                entry['disposition'] = 'confirmed'
        else:
            entry['reason'] = 'module refused or failed; see module log'
    result['wall_s'] = round(time.monotonic() - started, 1)
    snapshot.finish(result)
    common.write_json(out / 'result.json', result)
    print(json.dumps(result, indent=2) if args.json else
          f"x-sweep: {len(result['modules'])} module dispositions in {out / 'result.json'}")
    return 1
