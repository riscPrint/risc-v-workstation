import pytest
from rvw.cov.integer_sources import integer_source,FAMILIES
from rvw.cov.semantic import groups


@pytest.mark.parametrize('prefix',['rv','rv32','rv64'])
@pytest.mark.parametrize('family',sorted(FAMILIES))
def test_integer_bank_source_families(prefix,family):
    item = {'name':'fixture','source':f'extensions/{prefix}_{family}','args':['rs1','rs2']}
    assert integer_source(item,'rs1') and integer_source(item,'rs2')
    assert not integer_source(item,'rd')


@pytest.mark.parametrize('family',['f','d','zfh','v','unknown'])
def test_other_banks_are_not_inferred(family):
    assert not integer_source({'source':f'extensions/rv_{family}','args':['rs1']},'rs1')


@pytest.mark.parametrize('family',['a','zba','zbb','zbc','zbs','zicond'])
def test_plan_keeps_unseen_integer_value_bins(family):
    item={'name':'fixture','source':f'extensions/rv_{family}','args':['rs1','rs2']}
    generated=groups({'semantics':{'version':1,'privilege_modes':['M']}},[item])
    operands=[g for g in generated if g['name'].startswith('sem_fixture_')]
    assert len(operands)==2 and all(len(g['bins'])==7 for g in operands)
