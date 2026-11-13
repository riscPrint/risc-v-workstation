import sys
import pytest
from rvw.farm.service import Queue
from rvw.farm.costs import configure,report

pytestmark = pytest.mark.fast


def test_scope_cost_includes_infrastructure_without_inventing_gate_verdict(tmp_path):
    queue=Queue(tmp_path)
    configure(queue,'project:p',{'jobs':4},2.)
    queue.submit('a',[sys.executable,'-c',"import json;from pathlib import Path;Path('result.json').write_text(json.dumps(dict(schema='rvw.run/1',status='pass')))"] ,project='p')
    queue.submit('a',[sys.executable,'-c','raise SystemExit(1)'],project='p')
    queue.work_once();queue.work_once()
    result=report(queue,'project:p')
    assert result['recorded_dut_outcomes']['counts']=={'pass':1}
    assert result['cost_per_conclusive_dut_observation']==result['cost']
    assert result['usage']['jobs']==2
    assert result['recorded_gate_reports']==0
    assert result['cost_per_recorded_gate_report'] is None
    queue.submit('a',[sys.executable,'-c',"import json;from pathlib import Path;Path('verdict.json').write_text(json.dumps(dict(schema='rvw.verdict/2',verdict='reject',tests='fail')))"] ,project='p')
    queue.work_once()
    result=report(queue,'project:p')
    assert result['recorded_gate_reports']==1
    assert result['cost_per_recorded_gate_report']==result['cost']
    assert result['by_recorded_verdict']['reject']['cost_per_report']>0


def test_missing_rate_or_observations_keeps_unit_cost_null(tmp_path):
    queue=Queue(tmp_path)
    queue.submit('a',[sys.executable,'-c','pass'])
    queue.work_once()
    result=report(queue,'agent:a')
    assert result['cost'] is None
    assert result['cost_per_conclusive_dut_observation'] is None
    assert result['cost_per_recorded_gate_report'] is None
    assert result['recorded_dut_outcomes']['conclusive_observations']==0


def test_exhausted_retry_budget_retains_recorded_dut_failure(tmp_path):
    queue=Queue(tmp_path)
    job=queue.submit('a',[sys.executable,'-c',"import json;from pathlib import Path;Path('result.json').write_text(json.dumps(dict(schema='rvw.run/1',status='fail',fail_code=2)))"],retries=1,retry_on=['dut_failure'])
    configure(queue,'run:'+job['id'],{'jobs':1},1.)
    assert queue.work_once()['state']=='queued'
    assert queue.work_once() is None
    assert queue.jobs()[0]['state']=='budget_exhausted'
    assert report(queue,'run:'+job['id'])['recorded_dut_outcomes']['counts']=={'fail':1}
