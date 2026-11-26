"""Producer contracts used by VS Code. No native qualification is implied."""
import pytest
from rvw.mcp.envelope import envelope
from rvw.results.schema import Verdict

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('decision,tests,common', [
    ('accept', 'pass', 'pass'), ('reject', 'fail', 'fail'),
    ('inconclusive', 'incomplete', 'inconclusive'),
])
def test_c4_display_contract(decision, tests, common):
    raw = Verdict(verdict=decision, tests=tests).to_dict()
    assert Verdict.from_dict(raw).verdict == decision
    result = envelope(raw)
    assert result['schema'] == 'rvw.verdict/2'
    assert result.get('legacy_verdict', result['verdict']) == decision
    assert result['verdict'] == common
    assert result['tests'] == tests


def test_current_producers_match_extension_field_list(tmp_path):
    import json
    import runpy
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    contracts = json.loads((root / 'vscode/src/results/producer-fields.json').read_text())
    samples = runpy.run_path(str(root / 'vscode/scripts/producer-samples.py'))['produce'](tmp_path)
    types = {'array': list, 'object': dict, 'string': str, 'number': (int, float)}
    for name, contract in contracts.items():
        values = samples['gates'] if name == 'gate' else [samples[name]]
        for value in values:
            assert value['schema'] == contract['schema']
            for field, kind in contract['fields'].items():
                assert isinstance(value[field], types[kind]), (name, field)
    assert samples['lint']['status'] in ('clean', 'findings')
