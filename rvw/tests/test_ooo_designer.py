import json
from dataclasses import asdict
import pytest
from test_ooo import cfg, trace
from rvw.ooo.designer import report

pytestmark = pytest.mark.fast


def test_workload_report(tmp_path):
    c = asdict(cfg())
    c['latencies']['alu'] = 4
    (tmp_path/'config.json').write_text(json.dumps(c))
    trace(tmp_path/'trace.jsonl')
    plan = tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(schema='rvw.ooo-designer-plan/1',config='config.json',
        workloads=[dict(id='kernel',trace='trace.jsonl')],
        sensitivity_parameters=['latencies.alu'], search_parameters={'latencies.alu':[1,2,3,4]})))
    r = report(plan,tmp_path/'report')
    assert r['instret'] == 4
    assert len(r['next_three_changes']) == 3
    assert r['next_three_changes'][0]['speedup'] > 1
    assert r['workloads'][0]['attribution']['regions']['<unmapped>']['total_slots'] > 0
    assert 'Next three changes' in (tmp_path/'report/report.md').read_text()
    assert json.loads((tmp_path/'report/report.json').read_text())['ipc'] == r['ipc']
    with pytest.raises(FileExistsError):
        report(plan,tmp_path/'report')
