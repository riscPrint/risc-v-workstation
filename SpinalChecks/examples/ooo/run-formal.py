#!/usr/bin/env python3
"""Run bounded clean and negative controls after RVW_OOO_FORMAL generation."""
import importlib.util
import json
from pathlib import Path
import tomllib

from rvw.common.proc import run_group

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BUGS={'leak':'freelist.conservation:rename','double_allocate':'freelist.allocate:rename',
      'commit_order':'queue.order:rob','not_ready':'execution.operands:iq',
      'young_store':'store.forward_age:sq','stale_map':'recovery.map:rename',
      'lost_flush':'recovery.flush:rob'}


def main():
    spec=importlib.util.spec_from_file_location('connected', ROOT/'SpinalChecks/scripts/prepare-connected-formal.py')
    helper=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    out=HERE/'out/formal-jobs'
    out.mkdir(exist_ok=False)
    lines=['core="tiny-ooo"','config="depth16-seed-controls"']
    for variant in ['clean',*BUGS]:
        rtl=HERE/'out'/variant
        inventory=rtl/'TinyOoo.checks.json'
        data=json.loads(inventory.read_text())
        ids=[c['id'] for c in data['checks'] if c['status']=='inserted'] if variant=='clean' else [BUGS[variant]]
        helper.prepare(rtl,inventory,out/variant,ids,depth=16)
        plan=tomllib.loads((out/variant/'regress.toml').read_text())
        for prop in plan['property']:
            lines+=['','[[property]]', 'id='+json.dumps(variant+'_'+prop['id']),
                    'sby='+json.dumps(variant+'/'+prop['sby']),'top="TinyOoo"',
                    'requirements='+json.dumps(prop['requirements'])]
            if prop.get('activation_sby'):
                lines+=['activation_sby='+json.dumps(variant+'/'+prop['activation_sby'])]
    (out/'regress.toml').write_text('\n'.join(lines)+'\n')
    result=run_group([str(ROOT/'rvw/.venv/bin/rvw'),'formal','regress',str(out/'regress.toml'),
                      '--out',str(HERE/'out/formal-results'),'--jobs','3','--timeout','30'],
                     cwd=HERE,capture=True,timeout=180)
    (HERE/'out/formal.log').write_text(result.stdout+result.stderr)
    report_path=HERE/'out/formal-results/result.json'
    if not report_path.exists():
        raise RuntimeError('formal run did not write a result')
    report=json.loads(report_path.read_text())
    rows=[]
    for p in report['properties']:
        variant=p['id'].rsplit('_check_',1)[0]
        expected='bounded-pass' if variant=='clean' else 'failed'
        rows.append(dict(variant=variant,requirements=p.get('requirements',[]),
            formal_status=p['formal_status'],activation=p.get('activation'),
            expected=expected,matched=p['formal_status']==expected))
    summary=dict(schema='rvw.ooo-fixture-formal/1',depth=16,checks=rows,
                 status='matched' if all(r['matched'] for r in rows) else 'inconclusive',
                 limitations=['Bounded native fixture evidence, not an unbounded proof or core qualification.'])
    (HERE/'out/formal-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return 0 if summary['status']=='matched' else 1


if __name__=='__main__':
    raise SystemExit(main())
