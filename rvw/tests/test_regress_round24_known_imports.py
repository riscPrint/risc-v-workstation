"""Imports keep config scope and never silently ignore a signature selector."""
import pytest

from rvw.regress.known import load_known
from rvw.results import save_results
from test_regress_round19_core import _results
from test_regress_round24_known_core import call_known


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_known_import_keeps_result_config(fake, rvw, tmp_path, transport):
    source = tmp_path / 'input'
    save_results(_results('fake'), source)
    ok, data = call_known(transport, rvw, core=str(fake.config), from_=str(source), reason='triaged')
    assert ok, data
    waiver = load_known(tmp_path / 'known.toml')[0]
    assert waiver.config == 'small'
    assert not waiver.matches('isa', 'test', 'fail:7', 'large')
    from rvw.regress.compare import compare
    base, cand = _results('fake', 'pass'), _results('fake')
    base.config = cand.config = 'large'
    assert compare([base], [cand], [waiver]).verdict == 'reject'


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_known_import_config_filters_instead_of_relabelling(fake, rvw, tmp_path, transport):
    source = tmp_path / 'input'
    for config, signature in [('small', 'fail:3'), ('large', 'fail:7')]:
        result = _results('fake')
        result.config = config
        result.tests[0].signature = signature
        save_results(result, source / config)
    ok, data = call_known(transport, rvw, core=str(fake.config), from_=str(source),
                          config='large', reason='triaged')
    assert ok, data
    assert [(e.config, e.signature) for e in load_known(tmp_path / 'known.toml')] == [('large', 'fail:7')]


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
@pytest.mark.parametrize('options', [{'signature': 'fail:3'}, {'config': 'typo'}, {'id': 'typo'}])
def test_known_import_refuses_conflicts_or_empty_selection(fake, rvw, tmp_path, transport, options):
    source = tmp_path / 'input'
    save_results(_results('fake'), source)
    ok, data = call_known(transport, rvw, core=str(fake.config), from_=str(source), reason='triaged', **options)
    assert not ok, data
    assert not (tmp_path / 'known.toml').exists()


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_known_import_derives_legacy_assertion_signature(fake, rvw, tmp_path, transport):
    result = _results('fake')
    result.tests[0].status = 'assert'
    result.tests[0].signature = 'assert:core.sv: Assertion failed'
    result.tests[0].extra['message'] = 'core.sv:6: Assertion failed'
    source = tmp_path / 'input'
    save_results(result, source)
    ok, data = call_known(transport, rvw, core=str(fake.config), from_=str(source), reason='triaged')
    assert ok, data
    assert data['entries'][0]['signature'] == 'assert:core.sv:6'
