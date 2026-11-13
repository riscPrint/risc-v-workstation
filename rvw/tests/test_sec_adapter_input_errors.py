import json
import pytest
from rvw.sec import core_adapter

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('failure', [ValueError('unset environment variable in ${RVW_SEC_RTL}/VexTop.v'), FileNotFoundError('missing core binding')])
def test_adapter_cli_reports_expected_input_error(monkeypatch, capsys, failure):
    def reject(*args): raise failure
    monkeypatch.setattr(core_adapter, 'run_case', reject)
    assert core_adapter.main(['--binding', 'core.json', '--template', 'case.S', 'request.json', 'out']) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.err)
    assert result['status'] == 'error'
    assert result['error'] == str(failure)
    assert 'binding' in result['hint'] and 'RVW_SEC_RTL' in result['hint']
    assert not captured.out
