"""Security experiment results and bounded native commands."""
import datetime
import json
from pathlib import Path
from rvw.common.proc import run_group


def native(argv, cwd, timeout=90):
    from .budget import remaining, BudgetExpired
    timeout = remaining(timeout)
    r = run_group(['nice', '-n', '10', *argv], cwd=cwd, timeout=timeout, capture=True)
    if r.timed_out:
        raise BudgetExpired(f'{argv[0]} exceeded its {timeout:.1f} s wall budget')
    if r.returncode:
        raise ValueError(f'{argv[0]} failed: {r.stdout}\n{r.stderr}')
    return r.stdout or ''


def publish(out, technique, findings, complete, **details):
    out = Path(out)
    status = 'violation' if findings else 'no_leak_observed' if complete else 'inconclusive'
    report = dict(schema='rvw.sec/1', technique=technique, status=status,
                  findings=findings, complete=complete, **details)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    test = dict(id=technique, status={'violation':'fail', 'no_leak_observed':'pass',
                                    'inconclusive':'error'}[status], message=status)
    if status != 'no_leak_observed':
        test['signature'] = 'sec:'+technique+':'+status
    if status == 'inconclusive':
        test['inconclusive'] = 'missing or incomplete security evidence'
    suite = dict(schema='rvw.results/1', run_id=out.name, suite='sec-'+technique,
                 core='project', config='declared', source={},
                 created=datetime.datetime.now(datetime.timezone.utc).isoformat(), tests=[test])
    (out/'results.json').write_text(json.dumps(suite, indent=2)+'\n')
    return report
