import pytest
from rvw.soc.binding_help import diagnose, HELP
from rvw.soc.verify import verify, table
from test_soc_verify import MAP

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('kind', list(HELP))
def test_each_kind_names_specific_missing_bindings(kind):
    d=diagnose(kind,{},dict(regions=[dict(registers=[])]))
    assert d['missing_bindings']
    assert all(d['binding_help'][key] for key in d['missing_bindings'])
    assert all(key.startswith(('checks.'+kind+'.','map.')) for key in d['missing_bindings'])


def test_existing_command_needs_evidence_not_another_binding():
    d=diagnose('protocol',dict(command=['native-consumer']),dict(regions=[]))
    assert d['missing_bindings']==[] and 'fresh evidence' in d['needed_evidence']


def test_native_register_binding_is_complete():
    assert diagnose('registers',dict(command=['native-consumer'],write_read=['uart.scratch']),dict(regions=[dict(registers=[{}])]))['missing_bindings']==[]


def test_verify_exposes_help_without_promoting_generation(tmp_path):
    result=verify(MAP,tmp_path/'out')
    assert result['status']=='inconclusive'
    assert 'missing checks.decode.classpath_file' in table(result)
    for row in result['checks']:
        assert row['result']=='inconclusive' and row['missing_bindings'] and row['binding_help']
