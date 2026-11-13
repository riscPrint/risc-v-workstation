import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.formal import timeout_rerun as replay

pytestmark = pytest.mark.fast


def test_time_limit():
    assert replay.seconds('30m') == 1800
    assert replay.seconds('1.5h') == 5400
    for value in ('0','-1','nan','inf','1d'):
        with pytest.raises(ValueError): replay.seconds(value)


def test_select_only_timeout_checks():
    report=dict(rows=[dict(check='a',status='timeout'),
        dict(check='b',status='inconclusive',engines=[dict(status='timeout')]),
        dict(check='c',status='inconclusive',engines=[dict(status='pass'),dict(status='timeout')]),
        dict(check='d',status='failed'),dict(check='e',status='pass',instruction_activation=None),
        dict(check='f',status='pass',instruction_activation=dict(status='timeout')),
        dict(check='sail',status='inconclusive',native_status='timeout'),
        dict(check='g',status='inconclusive',native_attempts=[dict(task='cover',status='timeout')])])
    assert replay.timed_out_checks(report) == ['a','b','f-activation','g:cover','sail']


def test_historical_vex_inventory():
    root=Path(__file__).resolve().parents[2]
    previous=json.loads((root/'examples/vexriscv/formal/portfolio-results.json').read_text())
    assert len(replay.timed_out_checks(previous)) == 37


def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(replay,'installed',lambda: {k:dict(status='installed') for k in replay.ENGINES})
    (tmp_path/'model.sv').write_text('module top(input clk); always @(posedge clk) assert(0); endmodule')
    (tmp_path/'a.sby').write_text('[options]\nmode bmc\ndepth 5\ntimeout 1\n[engines]\nabc bmc3\n[script]\nread -formal model.sv\nprep -top top\n[files]\nmodel.sv\n')
    (tmp_path/'previous.json').write_text(json.dumps(dict(tests=[dict(id='a',status='timeout'),dict(id='b',status='pass')])))
    return dict(cores=[dict(name='tiny',previous='previous.json',jobs='.')])


def test_freeze_preserves_depth_and_source(tmp_path, monkeypatch):
    inputs(tmp_path,monkeypatch)
    mode,depth,hashes=replay.freeze(tmp_path/'a.sby',tmp_path/'frozen',['abc:bmc3','smtbmc:bitwuzla'])
    assert (mode,depth)==('bmc',5)
    config=(tmp_path/'frozen/replay.sby').read_text()
    assert 'timeout 1' not in config and 'depth 5' in config
    assert 'abc bmc3\nsmtbmc bitwuzla' in config
    assert (tmp_path/'frozen/input-0').read_bytes()==(tmp_path/'model.sv').read_bytes()
    assert hashes[0]['target']=='model.sv'


def test_freeze_rebinds_absolute_script_inputs(tmp_path,monkeypatch):
    inputs(tmp_path,monkeypatch)
    source=tmp_path/'a.sby'
    source.write_text(source.read_text().replace('read -formal model.sv','read -formal '+str(tmp_path/'model.sv')))
    replay.freeze(source,tmp_path/'frozen',['smtbmc:bitwuzla'])
    assert 'read -formal model.sv' in (tmp_path/'frozen/replay.sby').read_text()


def test_replay_writes_comparison_and_only_selected_job(tmp_path,monkeypatch):
    plan=inputs(tmp_path,monkeypatch)
    calls=[]
    def native(command, **kwargs):
        calls.append(command)
        model=kwargs['cwd']/'sby/src'
        model.mkdir(parents=True)
        (model/'replay-design.json').write_text('{"modules":{"top":{"cells":{"a":{"type":"$assert"}}}}}')
        kwargs['stdout'].write('engine_1 (smtbmc bitwuzla) returned pass\nDONE (PASS, rc=0)\n')
        return SimpleNamespace(returncode=0,timed_out=False)
    monkeypatch.setattr(replay,'run_group',native)
    result=replay.run(plan,tmp_path,tmp_path/'out',1800)
    assert len(calls)==1 and calls[0][:3]==['nice','-n','5']
    row=result['rows'][0]
    assert row['check']=='a' and row['status']=='bounded_pass'
    assert row['engine']=='smtbmc:bitwuzla' and row['timeout_s']==1800
    assert 'load_average_end' in row
    assert 'a | 5' in (tmp_path/'out/comparison.md').read_text()


def test_missing_capture_stays_visible(tmp_path,monkeypatch):
    plan=inputs(tmp_path,monkeypatch)
    (tmp_path/'a.sby').unlink()
    result=replay.run(plan,tmp_path,tmp_path/'out',1800)
    assert result['rows'][0]['status']=='error'
    assert result['rows'][0]['comparison']=='not_run'


def test_empty_selection_is_not_a_pass(tmp_path,monkeypatch):
    plan=inputs(tmp_path,monkeypatch)
    (tmp_path/'previous.json').write_text('{"tests":[]}')
    result=replay.run(plan,tmp_path,tmp_path/'out',1800)
    assert result['reason']=='no_timeout_checks' and result['status']=='inconclusive'


def test_missing_receipt_is_an_inventory_error(tmp_path):
    result=replay.run(dict(cores=[dict(name='absent',previous='missing.json')]),tmp_path,tmp_path/'out',1800)
    assert result['rows'][0]['check']=='receipt_inventory'
    assert result['rows'][0]['status']=='error'
