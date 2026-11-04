"""Native conformance subset and preflight refusal for the HDL profiles."""
import json
from pathlib import Path
import shutil

import pytest
from rvw.sim.hdl import load, run, TOOLS, PROFILES, require

EXAMPLES = Path(__file__).resolve().parents[2] / 'examples' / 'sim-semantics'


def available(backend):
    if any(not shutil.which(t) for t in TOOLS[backend]):
        pytest.skip(f'optional native tools absent: {backend}')


def native(tmp_path, name, backend=None):
    backend = backend or json.loads((EXAMPLES / f'{name}.json').read_text())['backend']
    available(backend)
    out = tmp_path / backend
    result = run(EXAMPLES / f'{name}.json', out, backend=backend)
    assert result['status'] == 'pass', (result, [p.read_text() for p in out.glob('*.stderr')])
    assert result['inputs'] and result['versions']
    return (out / result['jobs'][-1]['stdout']).read_text()


def test_four_state_reset(tmp_path):
    native(tmp_path, 'xreset')


def test_xfree_equivalence(tmp_path):
    a = native(tmp_path, 'xfree', 'icarus')
    b = native(tmp_path, 'xfree', 'verilator-timing')
    observations = lambda s: [x for x in s.splitlines() if x.startswith('OBS ')]
    assert observations(a) == observations(b)
    assert len(observations(a)) == 4


def test_timing_subset(tmp_path):
    native(tmp_path, 'timing')


def test_mixed_synthesis(tmp_path):
    native(tmp_path, 'mixed')


@pytest.mark.parametrize('backend', PROFILES)
@pytest.mark.parametrize('feature', ['sva', 'coverage', 'pessimistic_xprop', 'vhdl_events', 'full_sv'])
def test_unsupported(backend, feature):
    with pytest.raises(ValueError, match=feature):
        require(backend, [feature])


def test_refuse_x_on_two_state_before_output(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('preflight started a tool')
    monkeypatch.setattr('rvw.sim.hdl.run_group', forbidden)
    with pytest.raises(ValueError, match='four_state'):
        run(EXAMPLES / 'xreset.json', tmp_path / 'out', backend='verilator-timing')
    assert not (tmp_path / 'out').exists()


def test_mixed_has_no_four_state_claim():
    with pytest.raises(ValueError, match='four_state'):
        require('ghdl-yosys-icarus', ['four_state'])


@pytest.mark.parametrize('body', ['', 'assert (0) else $error("assertion failure"); $display("RVW_PASS"); $finish;', '$display("RVW_PASS"); $fatal(1, "failure after marker");', '$display("RVW_PASS"); forever #1;'])
def test_no_false_pass(tmp_path, body):
    available('icarus')
    (tmp_path / 'tb.sv').write_text('module tb; initial begin ' + body + ' end endmodule')
    p = tmp_path / 'manifest.json'
    p.write_text(json.dumps(dict(schema='rvw.hdl/1', backend='icarus', top='tb', sources=['tb.sv'])))
    result = run(p, tmp_path / 'out', timeout=3)
    assert result['status'] == 'error'


def test_missing_tool_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda _: None)
    with pytest.raises(ValueError, match='missing native tool'):
        run(EXAMPLES / 'xfree.json', tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('change', [{'requires': 'four_state'}, {'top': 'bad;name'}, {'vhdl_sources': ['counter.vhd']}, {'unknown': True}])
def test_bad_manifest(tmp_path, change):
    d = json.loads((EXAMPLES / 'xfree.json').read_text())
    d.update(change)
    p = tmp_path / 'm.json'
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        load(p)


def test_cli_profiles_and_refusal(tmp_path, capsys):
    from rvw.cli import main
    assert main(['regress', 'backends', '--hdl', '--json']) == 0
    profiles = json.loads(capsys.readouterr().out)
    assert profiles['verilator-timing']['values'] == '2-state'
    assert main(['regress', 'hdl', str(EXAMPLES / 'xreset.json'),
                 '--backend', 'verilator-timing', '--out', str(tmp_path / 'out'), '--json']) == 2
    assert 'four_state' in json.loads(capsys.readouterr().out)['error']
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_invalid_timeout(tmp_path, timeout):
    with pytest.raises(ValueError, match='timeout'):
        run(EXAMPLES / 'xfree.json', tmp_path / 'out', timeout=timeout)
    assert not (tmp_path / 'out').exists()


def test_existing_output_refused(tmp_path):
    available('icarus')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'results.json').write_text('old results')
    with pytest.raises(FileExistsError):
        run(EXAMPLES / 'xfree.json', out)
    assert (out / 'results.json').read_text() == 'old results'
