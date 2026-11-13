import json
from pathlib import Path
import pytest
from rvw.checks.commands.plan import plan

pytestmark=pytest.mark.fast


def project(tmp_path,spec=None):
    (tmp_path/'rvw.toml').write_text('[core]\nname="fixture"\n')
    if spec is not None:
        (tmp_path/'checks.generate.json').write_text(json.dumps(dict(schema='rvw.check-generation/1',**spec)))
    return tmp_path/'rvw.toml'


def test_missing_manifest_lists_exact_port_requirements(tmp_path):
    result=plan(project(tmp_path))
    rows={r['kind']:r for r in result['checks']}
    assert rows['freelist_conservation']['status']=='unbound'
    assert {'clk','reset','live','free_bits','alloc0'} <= set(rows['freelist_conservation']['needs'])
    assert {'issued','valid','ready'} <= set(rows['issue']['needs'])
    assert {'aw_fire','w_fire','b_fire'} <= set(rows['axi_lite']['needs'])
    assert not (tmp_path/'out').exists()


def test_plan_runs_generation_but_preserves_project_tree(tmp_path):
    p=project(tmp_path,dict(queues='micro.json'))
    (tmp_path/'micro.json').write_text(json.dumps(dict(schema='rvw.micro-checks/1',top='Top',rules=[
        dict(id='good',kind='mutex',ports=dict(clk='clk',reset='reset',grants='grant')),
        dict(id='missing',kind='fifo_order',ports=dict(clk='clk'))])))
    before=set(tmp_path.rglob('*'))
    result=plan(p)
    assert set(tmp_path.rglob('*'))==before
    rows={r['kind']:r for r in result['checks']}
    assert rows['mutex']['status']=='generated'
    assert rows['fifo_order']['status']=='unbound'
    assert 'pop_data' in rows['fifo_order']['bindings'][0]['missing']
    assert rows['fifo_order']['bindings'][0]['status']=='unsupported'


def test_invalid_selected_project_does_not_fallback(tmp_path):
    p=tmp_path/'rvw.toml';p.write_text('not valid toml')
    with pytest.raises(ValueError):
        plan(p)


def test_inventory_keeps_native_binding_separate(tmp_path):
    p=project(tmp_path)
    (tmp_path/'checks.json').write_text(json.dumps(dict(schema='rvw.checks/1',checks=[
        dict(id='custom:x',kind='custom',status='inserted',signals=dict(event=['event']),trigger_signal='trigger') ])))
    rows={r['kind']:r for r in plan(p,inventory='checks.json')['checks']}
    assert rows['custom']['native_inserted']==1
    assert rows['custom']['native_bindings'][0]['trigger_signal']=='trigger'


def test_mcp_plan_uses_short_tool_dispatch(tmp_path):
    from rvw.checks.commands.plan import mcp_tools
    from rvw.mcp.registry import Registry
    registry = Registry(mcp_tools())
    result = registry.call('checks_plan', {'project': str(project(tmp_path))})
    assert result['schema'] == 'rvw.check-plan/1'
    assert any(row['kind'] == 'req_rsp' for row in result['checks'])
