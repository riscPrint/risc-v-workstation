import json
from pathlib import Path
import pytest
from rvw.ooo.project import configuration

ROOT = Path(__file__).resolve().parents[2]


def description():
    d = json.loads((ROOT/'examples/boom/arch/large.json').read_text())
    d['ooo'] = {'latencies':{'alu':1, 'multiply':3, 'divide':34, 'load':4, 'store':2}}
    return d


def test_shared_widths_and_capacities():
    d = description()
    c = configuration(d)
    assert c.fetch_width == d['cpu']['fetchWidth']
    assert c.rename_width == d['cpu']['renameWidth']
    assert c.issue_entries == sum(q['entries'] for q in d['queues'])
    assert c.frontend['decode_width'] == d['cpu']['decodeWidth']
    d['ooo']['rename_width'] = 99
    with pytest.raises(ValueError, match='conflicts'):
        configuration(d)


def test_requires_explicit_own_execution_table():
    d = description(); del d['ooo']['latencies']
    with pytest.raises(ValueError, match='latencies'):
        configuration(d)


def test_gem5_validator_accepts_shared_description():
    import runpy
    validate = runpy.run_path(str(ROOT/'Arch/model.py'))['validate_description']
    d = description()
    assert validate(d)['ooo']['latencies']['multiply'] == 3
    d['ooo'] = []
    with pytest.raises(ValueError, match='ooo'):
        validate(d)


def test_same_description_runs_own_model_and_checks_preset(tmp_path):
    from test_ooo import trace
    from rvw.ooo.core import run
    d = description(); d['config'] = 'tiny'
    config, c2 = tmp_path/'model.json', tmp_path/'trace.jsonl'
    config.write_text(json.dumps(d)); trace(c2)
    r = run(config,c2)
    assert r['instret'] == 4
    assert r['config']['fetch_width'] == 8
    d['config'] = 'other'
    config.write_text(json.dumps(d))
    with pytest.raises(ValueError, match='selected config'):
        run(config,c2)
