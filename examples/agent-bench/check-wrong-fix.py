#!/usr/bin/env python3
"""Check a named-test pass against a hidden independent native workload."""
import argparse
import copy
import json
from pathlib import Path

from rvw.agent_bench.native import (git, load_pack, mutate, native_verdict,
                                    reference_checks, run_tests, verify_workspace)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--qualification', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    here = Path(__file__).resolve().parent
    pack, digest, base = load_pack(here / 'native.json')
    verify_workspace(pack, a.source, a.workspace)
    tasks = {t['id']: t for t in pack['tasks']}
    task = copy.deepcopy(tasks['xor'])
    task['private']['pass_to_pass'].append('rv32ui-p-sub')
    names = task['private']['fail_to_pass'] + task['private']['pass_to_pass']
    q = json.loads(a.qualification.read_text())
    baseline = {n: next(t['baseline'][n] for t in q['tasks'] if n in t['baseline']) for n in names}
    a.out.mkdir(parents=True, exist_ok=False)
    stages = {}
    applied = []
    try:
        for name, changes in [('seeded', [('xor', False)]),
                              ('wrong_fix', [('xor', True), ('sub', False)]),
                              ('reference', [('sub', True)])]:
            for target, reverse in changes:
                mutate(a.workspace, tasks[target]['private']['mutation'], reverse=reverse)
                if reverse:
                    applied.remove(target)
                else:
                    applied.append(target)
            git(a.workspace, 'add', 'src')
            git(a.workspace, 'commit', '-qm', name + ' independent repair check')
            if name == 'wrong_fix':
                old = baseline['rv32ui-p-xor']['identity']['source']['core_rev_full']
                (a.out / 'candidate.patch').write_text(git(a.workspace, 'diff', old, 'HEAD', '--', 'src') + '\n')
            stages[name] = run_tests(pack, base, a.workspace, a.out / name, names, 110)
            reference_checks(pack, base, a.workspace, stages[name], 30)
            (a.out / 'stages.json').write_text(json.dumps(stages, indent=2) + '\n')
        result = {'pack_sha256': digest, 'baseline': baseline, 'stages': stages,
                  'wrong_fix_verdict': native_verdict(task, baseline, stages['seeded'], stages['wrong_fix']),
                  'reference_verdict': native_verdict(task, baseline, stages['seeded'], stages['reference'])}
        (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        for name in reversed(applied):
            mutate(a.workspace, tasks[name]['private']['mutation'], reverse=True)
        if applied:
            git(a.workspace, 'add', 'src')
            git(a.workspace, 'commit', '-qm', 'restore independent check source')
        verify_workspace(pack, a.source, a.workspace)


if __name__ == '__main__':
    main()
