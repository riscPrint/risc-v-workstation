import json
import pytest
from rvw.regress.commands.applicability import plan

pytestmark = pytest.mark.fast


def test_missing_features_exclude_and_report_all_reasons(tmp_path):
    features = tmp_path / 'features.json'
    features.write_text(json.dumps(dict(schema='rvw.regress-features/1', capabilities=['xlen:32'])))
    result = plan(features)
    assert [x['name'] for x in result['suites'] if x['applicable']] == ['fence-rv32']
    sv32 = next(x for x in result['suites'] if x['name'] == 'mmu-sv32')
    assert 'satp:sv32' in sv32['missing']
    assert 'xlen:32' not in sv32['missing']
    features.write_text(json.dumps(dict(schema='rvw.regress-features/1', capabilities=['xlen:32', 'mode:S', 'mode:U', 'pmp', 'satp:sv32', 'ad:fault'])))
    result = plan(features)
    assert [x['name'] for x in result['suites'] if x['applicable']] == ['mmu-sv32', 'fence-rv32', 'random-privilege-rv32']


def test_project_catalog_and_invalid_declarations(tmp_path):
    features, catalog = tmp_path / 'f.json', tmp_path / 'c.json'
    features.write_text(json.dumps(dict(schema='rvw.regress-features/1', capabilities=['ext:a'])))
    catalog.write_text(json.dumps([dict(name='atomics', requires=['ext:a'])]))
    assert plan(features, catalog)['applicable'] == 1
    features.write_text('{}')
    with pytest.raises(ValueError, match='schema|expected'):
        plan(features, catalog)


def test_declared_isa_and_privilege_fields_and_xlen_conflict(tmp_path):
    features = tmp_path / 'features.json'
    data = dict(schema='rvw.regress-features/1', isa='rv64ima_zicsr_zifencei',
                privilege_modes='MSU', satp_modes=['sv39'], pmp_regions=8,
                irq_inputs=[3, 7, 11], capabilities=['ad:fault'])
    features.write_text(json.dumps(data))
    result = plan(features)
    applicable = {x['name'] for x in result['suites'] if x['applicable']}
    assert {'mmu-sv39', 'privilege-controls', 'scheduled-wfi', 'amo-rv64'} <= applicable
    assert 'mmu-sv32' not in applicable and 'memory-concurrent' not in applicable
    data['capabilities'].append('xlen:32')
    features.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='XLEN'):
        plan(features)
