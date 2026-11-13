"""CSR compatibility is metadata, never a DUT pass or a reason to skip a test."""
import json
from pathlib import Path
import pytest
from rvw.regress.act4 import selection
from rvw.regress.act4_csr import csr_contract
from rvw.cosim.platform import Platform

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_supervisor_missing_sm_csr_is_a_finding():
    plan = selection(ROOT/'examples/vexiiriscv/rvw/act4-supervisor/profile.json')
    contract = plan['csr_contract']
    assert contract['missing_required'] == 1
    row, = contract['registers']
    assert row == dict(name='mhpmevent3', address=0x323, present=False,
                       required=True, extension='sm', status='missing-required')
    assert plan['include_priv_tests'] is True
    assert 'sm' in plan['extensions']


def test_omitted_csrs_are_unknown_and_binding_is_required(tmp_path):
    platform = Platform.load(None, ROOT/'examples/vexiiriscv/rvw/platform32.json')
    data = dict(csr_model='model.json',platform='platform.json',extensions={'sm':'= 1.12.0'})
    model = dict(schema='rvw.csr-selection/1',xlen=32,csrs=[],binding={'platform':'platform.json'})
    p = tmp_path/'model.json'
    p.write_text(json.dumps(model))
    assert csr_contract(tmp_path/'profile.json',data,platform)['registers'] == []
    model['binding']['platform'] = 'other.json'
    p.write_text(json.dumps(model))
    with pytest.raises(ValueError,match='bind'):
        csr_contract(tmp_path/'profile.json',data,platform)
    model['xlen']=64
    p.write_text(json.dumps(model))
    with pytest.raises(ValueError,match='XLEN'):
        csr_contract(tmp_path/'profile.json',data,platform)
