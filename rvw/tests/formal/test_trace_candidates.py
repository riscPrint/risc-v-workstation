import pytest
from rvw.formal.trace_candidates import mine, scala

pytestmark = pytest.mark.fast


def test_refuted_candidates_are_dropped_and_dead_guards_are_not_candidates():
    signals = dict(valid=1, fire=1, idle=1, dead=1, payload=8)
    rows = [dict(valid=1,fire=1,idle=0,dead=0,payload=2),
            dict(valid=1,fire=0,idle=0,dead=0,payload=2),
            dict(valid=0,fire=0,idle=1,dead=0,payload=2)] * 3
    result = mine(signals, [rows], [['fire','idle']])
    specs = {(c['kind'],tuple(c['signals'])) for c in result['candidates']}
    assert ('implies',('fire','valid')) in specs
    assert ('implies',('valid','fire')) not in specs
    assert ('stable',('valid','payload')) in specs
    assert ('onehot0',('fire','idle')) in specs
    assert not any(kind == 'implies' and names[0] == 'dead' for kind,names in specs)
    assert result['refuted'] > 0 and result['inactive'] > 0
    assert 'overlap = false' in scala(result)
    assert result['scope'].startswith('supplied finite traces only')


def test_no_transition_across_program_boundaries():
    result = mine(dict(g=1,p=8), [[dict(g=1,p=0)]*3, [dict(g=1,p=255)]*3])
    assert any(c['kind']=='stable' for c in result['candidates'])
    result = mine(dict(g=1,p=8), [[dict(g=1,p=0)]*3+[dict(g=1,p=255)]*3])
    assert not any(c['kind']=='stable' for c in result['candidates'])


@pytest.mark.parametrize('row', [dict(g=1), dict(g=2,p=1), dict(g=1,p='x')])
def test_bad_samples_refused(row):
    with pytest.raises(ValueError):
        mine(dict(g=1,p=8), [[row]])


def test_cli_and_mcp(tmp_path, capsys):
    import json
    from rvw.cli import main
    from rvw.formal.commands.trace_mine import mcp_tools
    manifest = tmp_path/'signals.json'
    trace = tmp_path/'trace.jsonl'
    manifest.write_text(json.dumps(dict(signals=dict(a=1,b=1))))
    trace.write_text('{"a":1,"b":1}\n'*3)
    out = tmp_path/'mined'
    assert main(['formal','trace-mine','--manifest',str(manifest),'--trace',str(trace),'--out',str(out),'--json']) == 0
    assert json.loads(capsys.readouterr().out)['samples'] == 3
    assert (out/'MinedProperties.scala').exists()
    assert mcp_tools()[0].name == 'formal_trace_mine'
