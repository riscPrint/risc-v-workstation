import json
import pytest
from rvw.formal import isa

pytestmark=pytest.mark.fast


def bounded(monkeypatch):
    from rvw.formal import riscv,isa_activation
    def fake(cfg,out,*a):
        out.mkdir()
        (out/'results.json').write_text(json.dumps(dict(tests=[],bounded_depth=20)))
    monkeypatch.setattr(riscv,'run',fake)
    monkeypatch.setattr(isa_activation,'run',lambda *a:None)


def test_conditional_instruction_proof_keeps_assumptions(tmp_path,monkeypatch):
    from rvw.formal import riscv_proof
    bounded(monkeypatch)
    assumptions=[dict(source_excerpt='assume(bus_ready);',predicate_bits=[7],enable_bits=['1'])]
    native=dict(check='insn_add_ch0',status='inconclusive',assumptions=assumptions,
                environment_check='activation_not_checked',condition_model=dict(path='design.json',sha256='abc'),
                winner=dict(status='pass'),cross_check='inconclusive',rows=[])
    monkeypatch.setattr(riscv_proof,'run',lambda *a:dict(rows=[native]))
    report=isa.run(dict(checks=['insn_add_ch0','cover'],depth=20),tmp_path/'out',1,'external',unbounded=True)
    row=report['rows'][0]
    assert row['status']=='inconclusive' and row['conditional_native_proof']
    assert row['assumptions']==assumptions and row['condition_model']['sha256']=='abc'
    assert report['status']=='inconclusive'


def test_abstraction_conditions_follow_the_selected_variant(tmp_path,monkeypatch):
    from rvw.formal import riscv_abstract
    bounded(monkeypatch)
    assumptions=[dict(source_excerpt='assume(single_flight);')]
    native=dict(assumptions=assumptions,environment_check='activation_not_checked',rows=[])
    result=dict(rows=[dict(check='insn_lui_ch0',status='inconclusive',conditional_native_proof=True,
                           native_portfolio=native)],restriction='single_flight',
                pipeline_restriction=True,ram_abstraction=False)
    monkeypatch.setattr(riscv_abstract,'run',lambda *a,**kw:result)
    manifest=tmp_path/'manifest.json';manifest.write_text('{}')
    report=isa.run(dict(checks=['insn_lui_ch0','cover'],depth=20),tmp_path/'out',1,'external',abstraction=manifest)
    row=next(r for r in report['rows'] if r['check'].endswith(':abstraction'))
    assert row['assumptions']==assumptions and not row['abstraction']['ram_abstraction']
    assert row['status']=='inconclusive' and row['conditional_native_proof']


def test_round_conditions_are_not_lost(tmp_path):
    (tmp_path/'round-0').mkdir()
    native=dict(assumptions=[dict(cell='assume_reset')])
    (tmp_path/'round-0/result.json').write_text(json.dumps(native))
    assert isa.abstraction_native(dict(rounds=[dict(result='round-0/result.json')]),tmp_path)==native


def test_timeout_without_winner_is_not_a_proof(tmp_path,monkeypatch):
    from rvw.formal import riscv_proof
    bounded(monkeypatch)
    monkeypatch.setattr(riscv_proof,'run',lambda *a:dict(rows=[dict(check='insn_add_ch0',status='inconclusive',winner=None)]))
    report=isa.run(dict(checks=['insn_add_ch0','cover'],depth=20),tmp_path/'out',1,'external',unbounded=True)
    assert not report['rows'][0]['conditional_native_proof']
    assert report['rows'][0]['assumptions'] is None


def test_disagreement_does_not_label_a_conditional_proof(tmp_path,monkeypatch):
    from rvw.formal import riscv_proof
    bounded(monkeypatch)
    native=dict(check='insn_add_ch0',status='inconclusive',winner=dict(status='pass'),cross_check='disagree')
    monkeypatch.setattr(riscv_proof,'run',lambda *a:dict(rows=[native]))
    report=isa.run(dict(checks=['insn_add_ch0','cover'],depth=20),tmp_path/'out',1,'external',unbounded=True)
    assert not report['rows'][0]['conditional_native_proof']
